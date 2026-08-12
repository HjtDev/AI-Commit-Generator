import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from ui.backend import dependencies
from ui.backend.main import app


class FakeLLMService:
    """Test double standing in for core.llm.LLMService.

    Real network calls are out of scope here (core/tests/test_llm.py
    already covers LLMService itself against a mocked OpenAI client) --
    this exists purely to drive the backend's error-mapping and streaming
    logic through every path a real provider could put it on.
    """

    def __init__(self, mode: str):
        self.mode = mode

    async def generate(self, diff: str, hint: str = ""):
        if self.mode == "ok":
            return "feat: add x", "- did a thing"
        if self.mode == "unusable":
            raise ValueError("LLM returned an empty output.")
        if self.mode == "connection_error":
            raise openai.APIConnectionError(
                message="connection refused", request=httpx.Request("POST", "http://fake")
            )
        if self.mode == "auth_error":
            resp = httpx.Response(401, request=httpx.Request("POST", "http://fake"))
            raise openai.AuthenticationError("bad key", response=resp, body=None)
        raise AssertionError(f"unhandled mode {self.mode!r} for generate()")

    async def stream(self, diff: str, hint: str = ""):
        if self.mode == "ok":
            for chunk in ["```\n", "feat: add x\n", "```\n", "```\n", "- did a thing\n", "```\n"]:
                yield chunk
        elif self.mode == "fail_immediately":
            raise openai.APIConnectionError(
                message="connection refused", request=httpx.Request("POST", "http://fake")
            )
            yield  # pragma: no cover -- keeps this an async generator function
        elif self.mode == "fail_midstream":
            yield "```\nfeat: partial\n```\n"
            raise openai.APIConnectionError(
                message="dropped mid-stream", request=httpx.Request("POST", "http://fake")
            )
        else:
            raise AssertionError(f"unhandled mode {self.mode!r} for stream()")


@pytest.fixture
def use_llm(client: TestClient):
    """Installs a FakeLLMService of the given mode as the llm service
    factory dependency for the current test.
    """

    def _use(mode: str) -> FakeLLMService:
        fake = FakeLLMService(mode)

        def factory():
            return lambda model=None, endpoint=None: fake

        app.dependency_overrides[dependencies.get_llm_service_factory] = factory
        return fake

    return _use


class TestGenerate:
    def test_ok(self, client: TestClient, use_llm):
        use_llm("ok")
        r = client.post("/llm/generate", json={"diff": "diff --git a/x b/x"})
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "feat: add x"
        assert body["body"] == "- did a thing"
        assert body["err_code"] == 0

    def test_empty_diff_returns_400(self, client: TestClient):
        r = client.post("/llm/generate", json={"diff": "   "})
        assert r.status_code == 400
        assert r.json()["err_code"] == 201

    def test_unusable_output_returns_502(self, client: TestClient, use_llm):
        use_llm("unusable")
        r = client.post("/llm/generate", json={"diff": "x"})
        assert r.status_code == 502
        assert r.json()["err_code"] == 205

    def test_connection_error_returns_502(self, client: TestClient, use_llm):
        use_llm("connection_error")
        r = client.post("/llm/generate", json={"diff": "x"})
        assert r.status_code == 502
        assert r.json()["err_code"] == 202

    def test_auth_error_returns_502(self, client: TestClient, use_llm):
        use_llm("auth_error")
        r = client.post("/llm/generate", json={"diff": "x"})
        assert r.status_code == 502
        assert r.json()["err_code"] == 203


class TestStream:
    def test_ok_streams_then_emits_done_event_with_parsed_output(self, client: TestClient, use_llm):
        use_llm("ok")
        r = client.post("/llm/stream", json={"diff": "diff --git a/x b/x"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert "event: done" in r.text
        assert '"title": "feat: add x"' in r.text
        assert '"body": "- did a thing"' in r.text

    def test_empty_diff_returns_400_before_streaming_starts(self, client: TestClient):
        r = client.post("/llm/stream", json={"diff": ""})
        assert r.status_code == 400
        assert r.headers["content-type"].startswith("application/json")
        assert r.json()["err_code"] == 201

    def test_priming_failure_is_a_real_http_status_not_a_broken_stream(
            self, client: TestClient, use_llm
    ):
        # The critical regression test: LLMService.stream() is an async
        # generator, so a connection failure only surfaces on the first
        # __anext__. If that first pull happened inside the SSE endpoint
        # itself (after headers are already on the wire), this would come
        # back as `200 OK` with a silently truncated body -- the single
        # most common real failure mode, made invisible. Priming inside a
        # Depends() is what prevents that.
        use_llm("fail_immediately")
        r = client.post("/llm/stream", json={"diff": "x"})
        assert r.status_code == 502
        assert r.headers["content-type"].startswith("application/json")
        assert r.json()["err_code"] == 202

    def test_midstream_failure_is_an_in_band_sse_error_event(self, client: TestClient, use_llm):
        # The complementary case: once at least one chunk has already been
        # sent, the HTTP status is committed and can never change again --
        # this MUST surface as an in-band `error` event, not a status code.
        use_llm("fail_midstream")
        r = client.post("/llm/stream", json={"diff": "x"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert "feat: partial" in r.text
        assert "event: error" in r.text
        assert '"err_code": 202' in r.text
