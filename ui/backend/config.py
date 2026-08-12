from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "git-auto-commit"
    version: str = "0.4.0"

    # We don't pass it to FastAPI app to use our own exception handler
    debug: bool = False

    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_COMMIT_UI_",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
