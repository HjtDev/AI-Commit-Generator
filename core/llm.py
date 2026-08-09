from typing import AsyncGenerator, Tuple
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
import re


class LLMService:
    COMMIT_TYPES = (
        "Feature",
        "Fix",
        "Refactor",
        "Polish",
        "Perf",
        "Docs",
        "Style",
        "Test",
        "Chore",
        "Build",
        "CI",
        "Revert",
    )
    _STRAY_FENCE_LINE_RE = re.compile(r"^`{4,}[a-zA-Z]*[ \t]*$\n?", re.MULTILINE)
    _FENCE_RE = re.compile(r"```[a-zA-Z]*\n?(.*?)```", re.DOTALL)

    def __init__(
            self,
            endpoint: str,
            model: str,
            api_key: str = "AI-COMMIT",
            timeout: int = 30,
            retries: int = 3,
            conventional: bool = False,
            system_prompt: str = "",
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self.model = model
        self.conventional = conventional
        self.system_prompt = system_prompt
        self.client = AsyncOpenAI(
            base_url=self.endpoint,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.retries,
        )

    async def generate(
            self, diff: str, hint: str = "", system_prompt: str = ""
    ) -> Tuple[str, str]:
        messages = self._build_openai_prompt(
            diff, hint, system_prompt or self.system_prompt
        )

        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, stream=False
        )

        raw_output = response.choices[0].message.content
        if raw_output is None:
            raise RuntimeError("Failed to retrieve LLM output.")
        return self.parse_commit_output(raw_output)

    async def stream(
            self, diff: str, hint: str = "", system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        messages = self._build_openai_prompt(
            diff, hint, system_prompt or self.system_prompt
        )

        stream_response = await self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True
        )

        async for chunk in stream_response:
            content = chunk.choices[0].delta.content or ""
            if content:
                yield content

    @classmethod
    def to_conventional(cls, system_prompt: str) -> str:
        for commit_type in cls.COMMIT_TYPES:
            system_prompt = system_prompt.replace(
                commit_type, commit_type.lower()
            )
        return system_prompt

    def _build_prompt(self, diff: str, hint: str) -> str:
        return f"DIFF:\n{diff}\nHINT:\n{hint}" if hint else f"DIFF:\n{diff}"

    def _build_system_prompt(self, system_prompt: str) -> str:
        return (
            self.to_conventional(system_prompt)
            if self.conventional
            else system_prompt
        )

    def _build_openai_prompt(
            self, diff: str, hint: str, system_prompt: str
    ) -> list[ChatCompletionMessageParam]:
        prompt = self._build_prompt(diff, hint)
        messages = []
        if system_prompt:
            processed_system_prompt = self._build_system_prompt(system_prompt)
            messages.append(
                {"role": "system", "content": processed_system_prompt}
            )
        messages.append({"role": "user", "content": prompt})
        return messages

    @classmethod
    def parse_commit_output(cls, raw_output: str) -> Tuple[str, str]:
        # If you try removing pairs of fences due to models inconsistency it will fail
        cleaned = cls._STRAY_FENCE_LINE_RE.sub("", raw_output.strip()).strip()
        blocks = [m.group(1).strip() for m in cls._FENCE_RE.finditer(cleaned)]

        if len(blocks) >= 2:
            # The expected two-fence contract: block 1 is the title,
            # every following block is joined into the description.
            title_lines = [ln.strip() for ln in blocks[0].splitlines() if ln.strip()]
            summary = title_lines[0] if title_lines else ""
            body_lines = [
                ln.rstrip()
                for block in blocks[1:]
                for ln in block.splitlines()
                if ln.strip()
            ]
            formatted_desc = "\n".join(body_lines).strip()
        else:
            # a single fenced block, or no fences at all —
            # treat the first non-empty line as the title.
            text = blocks[0] if blocks else cleaned
            lines = [line.rstrip() for line in text.splitlines() if line.strip()]
            summary = lines[0].strip() if lines else ""
            formatted_desc = "\n".join(lines[1:]).strip()

        if not summary:
            raise ValueError("LLM returned an empty output.")
        return summary, formatted_desc
