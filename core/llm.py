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

        return self._parse_commit_output(raw_output)

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
    def _parse_commit_output(cls, raw_output: str) -> Tuple[str, str]:
        cleaned = raw_output.strip()

        # Remove outer triple-backtick Markdown blocks if present
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        lines = [
            line.rstrip() for line in cleaned.splitlines() if line.strip()
        ]

        if not lines:
            raise ValueError("LLM returned an empty output.")

        summary = lines[0].strip()
        description_lines = lines[1:]
        formatted_desc = "\n".join(description_lines).strip()

        return summary, formatted_desc
