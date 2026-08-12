from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Self
import json

CONFIG_FILE = Path(__file__).parent / "config.json"

class Config(BaseSettings):
    endpoint: str = "127.0.0.1:1234"
    api_key: str | None = None
    model: str = "qwen2.5-coder-3b-instruct"
    conventional: bool = True
    auto_commit_on_success: bool = False
    timeout: int = 30
    retries: int = 3
    default_max_diff_chars: int = 128000

    # Load from environment variables
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_COMMIT_",
        case_sensitive=False,
        extra="ignore"
    )

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> Self:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls.model_validate(data)
            except (json.JSONDecodeError, Exception):
                pass

        # Creates a default instance and saves it
        config = cls()
        config.save(path)
        return config

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.write_text(
            self.model_dump_json(indent=2),
            encoding="utf-8"
        )

    def reset_to_default(self, path: Path = CONFIG_FILE) -> Self:
        default_config = self.__class__()
        default_config.save(path)
        return default_config


def mask_secret(value: str | None) -> str | None:
    if not value:
        return value
    return value[:4] + "…" + value[-2:] if len(value) > 8 else "****"
