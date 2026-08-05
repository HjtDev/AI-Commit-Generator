from unittest.mock import AsyncMock, MagicMock
import pytest
from core.llm import LLMService  # Adjust import path accordingly


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def llm_service() -> LLMService:
    """Provides a standard LLMService instance."""
    return LLMService(
        endpoint="http://localhost:1234/v1",
        model="qwen2.5-coder-3b-instruct",
        conventional=False,
        system_prompt="Generate commit message for Feature, Fix, or Refactor.",
    )


@pytest.fixture
def conventional_llm_service() -> LLMService:
    """Provides an LLMService instance with conventional commit support enabled."""
    return LLMService(
        endpoint="http://localhost:1234/v1",
        model="qwen2.5-coder-3b-instruct",
        conventional=True,
        system_prompt="Generate commit message for Feature, Fix, or Refactor.",
    )


# ---------------------------------------------------------------------------
# Unit Tests: Prompt Construction & Parsing Logic
# ---------------------------------------------------------------------------

class TestPromptConstruction:
    def test_to_conventional_lowercases_commit_types(self):
        prompt = "Create a Feature or Fix commit."
        converted = LLMService.to_conventional(prompt)
        assert converted == "Create a feature or fix commit."

    def test_build_prompt_with_and_without_hint(self, llm_service: LLMService):
        diff = "diff --git a/main.py"
        hint = "Add error handling"

        # With hint
        assert llm_service._build_prompt(diff, hint) == f"DIFF:\n{diff}\nHINT:\n{hint}"
        # Without hint
        assert llm_service._build_prompt(diff, "") == f"DIFF:\n{diff}"

    def test_build_system_prompt_respects_conventional_flag(
        self, llm_service: LLMService, conventional_llm_service: LLMService
    ):
        raw_prompt = "Create a Feature commit."

        # Non-conventional leaves string as-is
        assert llm_service._build_system_prompt(raw_prompt) == "Create a Feature commit."

        # Conventional converts registered types to lower case
        assert conventional_llm_service._build_system_prompt(raw_prompt) == "Create a feature commit."

    def test_build_openai_prompt_uses_fallback_system_prompt(self, llm_service: LLMService):
        diff = "some diff"

        # Default system prompt
        messages = llm_service._build_openai_prompt(diff, "", llm_service.system_prompt)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == llm_service.system_prompt
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "DIFF:\nsome diff"


class TestOutputParsing:
    def test_parse_commit_output_standard_format(self):
        raw = "feat(auth): add login endpoint\n- add jwt handler\n- add test cases"
        summary, description = LLMService._parse_commit_output(raw)

        assert summary == "feat(auth): add login endpoint"
        assert description == "- add jwt handler\n- add test cases"

    def test_parse_commit_output_strips_markdown_code_fences(self):
        raw = "```git\nfix(api): resolve timeout bug\n- increase HTTP timeout to 30s\n```"
        summary, description = LLMService._parse_commit_output(raw)

        assert summary == "fix(api): resolve timeout bug"
        assert description == "- increase HTTP timeout to 30s"

    def test_parse_commit_output_empty_raises_value_error(self):
        with pytest.raises(ValueError, match="LLM returned an empty output"):
            LLMService._parse_commit_output("   \n\n  ")


# ---------------------------------------------------------------------------
# Async Tests: API Generation & Streaming
# ---------------------------------------------------------------------------

class TestLLMServiceAsyncCalls:
    @pytest.mark.asyncio
    async def test_generate_success(self, llm_service: LLMService, mocker):
        # 1. Mock OpenAI response object structure
        mock_choice = MagicMock()
        mock_choice.message.content = "feat: add feature\n- detailed line 1\n- detailed line 2"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        # 2. Patch AsyncOpenAI chat.completions.create method
        mocker.patch.object(
            llm_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

        # 3. Call method
        summary, description = await llm_service.generate(diff="test diff")

        assert summary == "feat: add feature"
        assert description == "- detailed line 1\n- detailed line 2"
        llm_service.client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_raises_when_content_is_none(self, llm_service: LLMService, mocker):
        mock_choice = MagicMock()
        mock_choice.message.content = None

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mocker.patch.object(
            llm_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        )

        with pytest.raises(RuntimeError, match="Failed to retrieve LLM output"):
            await llm_service.generate(diff="test diff")

    @pytest.mark.asyncio
    async def test_stream_chunks(self, llm_service: LLMService, mocker):
        # 1. Create mock chunks
        def create_chunk(text: str):
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = text
            return chunk

        chunks = [create_chunk("feat: "), create_chunk("add "), create_chunk("streaming")]

        # 2. Mock async generator returned by stream=True
        async def async_chunk_generator():
            for chunk in chunks:
                yield chunk

        mocker.patch.object(
            llm_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=async_chunk_generator(),
        )

        # 3. Stream chunks and collect output
        collected = []
        async for chunk in llm_service.stream(diff="test diff"):
            collected.append(chunk)

        assert "".join(collected) == "feat: add streaming"