from typing import AsyncGenerator, Callable, Optional, Tuple
from fastapi import APIRouter, Depends
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent
from core.llm import LLMService
import openai
from ..dependencies import get_llm_service_factory
from ..errors import APIError
from ..openapi import build_responses
from ..schemas.base import ErrorResponse
from ..schemas.llm import GenerateRequest, GenerateSuccessResponse, LlmRes

router = APIRouter(prefix="/llm", tags=["LLM"])

LlmFactory = Callable[..., LLMService]

# These are the responses /llm/stream returns BEFORE the SSE body starts --
# real HTTP errors from the priming dependency below, always application/json
# (verified via TestClient). FastAPI's OpenAPI generator additionally injects
# an empty sibling "text/event-stream" entry into these same status codes,
# because it derives the additional-response schema's media type from the
# route's own response_class rather than from what's actually declared here.
# Harmless and cosmetic -- the application/json entry with the real schema
# and example is present and correct alongside it -- so left as-is rather
# than fighting framework internals for a docs-only duplicate.
_PREFLIGHT_RESPONSES = build_responses(
    LlmRes.EMPTY_DIFF,
    LlmRes.ENDPOINT_UNREACHABLE,
    LlmRes.AUTH_FAILED,
    LlmRes.PROVIDER_ERROR,
)


def _map_provider_error(e: Exception) -> APIError:
    # First checking for openai common known errors
    if isinstance(e, openai.AuthenticationError):
        return APIError(LlmRes.AUTH_FAILED, detail=str(e))
    if isinstance(e, openai.APIConnectionError):  # includes APITimeoutError
        return APIError(LlmRes.ENDPOINT_UNREACHABLE, detail=str(e))
    return APIError(LlmRes.PROVIDER_ERROR, detail=str(e))


@router.post(
    "/generate",
    response_model=GenerateSuccessResponse,
    name="Generate Commit Message",
    description="Generate a commit title/body from a diff (blocks until the full response is ready).",
    responses=build_responses(
        LlmRes.EMPTY_DIFF,
        LlmRes.ENDPOINT_UNREACHABLE,
        LlmRes.AUTH_FAILED,
        LlmRes.PROVIDER_ERROR,
        LlmRes.UNUSABLE_OUTPUT,
    ),
)
async def generate(
        payload: GenerateRequest,
        llm_factory: LlmFactory = Depends(get_llm_service_factory),
):
    if not payload.diff.strip():
        raise APIError(LlmRes.EMPTY_DIFF)

    service = llm_factory(model=payload.model, endpoint=payload.endpoint)

    try:
        title, body = await service.generate(payload.diff, payload.hint)
    except openai.APIError as e:
        raise _map_provider_error(e)
    except (ValueError, RuntimeError) as e:
        # ValueError: parse_commit_output's "LLM returned an empty output."
        # RuntimeError: LLMService.generate's "Failed to retrieve LLM output."
        raise APIError(LlmRes.UNUSABLE_OUTPUT, detail=str(e))

    return GenerateSuccessResponse.from_spec(LlmRes.SUCCESS.value, title=title, body=body)


async def _prime_stream(
        payload: GenerateRequest,
        llm_factory: LlmFactory = Depends(get_llm_service_factory),
) -> Tuple[AsyncGenerator[str, None], Optional[str]]:
    """Runs as a Depends() -- i.e. entirely BEFORE the SSE response begins.

    This is the fix for the failure mode a global exception handler cannot
    reach: `LLMService.stream()` is an async generator, so the network call
    inside it doesn't run until the first `__anext__`. If that first pull
    happened inside the streaming endpoint itself, a dead/unreachable model
    provider -- the single most common failure for this whole product --
    would come back as `200 OK` with a silently truncated body, because
    headers are already sent before an SSE generator body executes at all.

    Pulling that first chunk here instead runs it during normal dependency
    resolution, which happens strictly before any response is constructed --
    verified empirically: an APIError raised from a Depends() on an
    EventSourceResponse route renders as a normal JSON error with the
    correct status code, not a broken stream.
    """
    if not payload.diff.strip():
        raise APIError(LlmRes.EMPTY_DIFF)

    service = llm_factory(model=payload.model, endpoint=payload.endpoint)
    agen = service.stream(payload.diff, payload.hint)

    try:
        first_chunk = await agen.__anext__()
    except StopAsyncIteration:
        first_chunk = None
    except openai.APIError as e:
        raise _map_provider_error(e)

    return agen, first_chunk


@router.post(
    "/stream",
    response_class=EventSourceResponse,
    name="Stream Commit Message",
    description=(
        "Stream a commit title/body from a diff via Server-Sent Events. "
        "A failure before the first token is a normal HTTP error response "
        "(see below); a failure mid-stream, after tokens have already been "
        "sent, arrives instead as an in-band `error` SSE event, since HTTP "
        "status can no longer change once streaming has started."
    ),
    responses=_PREFLIGHT_RESPONSES,
)
async def stream_commit_message(primed: Tuple[AsyncGenerator[str, None], Optional[str]] = Depends(_prime_stream)):
    agen, first_chunk = primed
    buffer = first_chunk or ""

    try:
        if first_chunk is not None:
            yield ServerSentEvent(data=first_chunk)
        async for chunk in agen:
            buffer += chunk
            yield ServerSentEvent(data=chunk)
    except openai.APIError as e:
        err = _map_provider_error(e)
        yield ServerSentEvent(
            event="error",
            data=ErrorResponse.from_spec(err.spec, detail=err.detail).model_dump(),
        )
        return

    try:
        title, body = LLMService.parse_commit_output(buffer)
    except ValueError as e:
        yield ServerSentEvent(
            event="error",
            data=ErrorResponse.from_spec(LlmRes.UNUSABLE_OUTPUT.value, detail=str(e)).model_dump(),
        )
        return

    yield ServerSentEvent(
        event="done",
        data=GenerateSuccessResponse.from_spec(LlmRes.SUCCESS.value, title=title, body=body).model_dump(),
    )
