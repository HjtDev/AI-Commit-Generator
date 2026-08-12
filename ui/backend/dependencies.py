from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Callable, Optional
from fastapi import Depends
from core.git import Git
from core.llm import LLMService, build_llm_service
from core.settings import CONFIG_FILE, Config


def get_config_path() -> Path:
    return CONFIG_FILE


def get_config(path: Path = Depends(get_config_path)) -> Config:
    return Config.load(path)


def get_git_factory() -> Callable[..., Git]:
    return Git


def get_llm_service_factory(
        config: Config = Depends(get_config),
) -> Callable[..., LLMService]:

    def _factory(model: Optional[str] = None, endpoint: Optional[str] = None) -> LLMService:
        return build_llm_service(config, model=model, endpoint=endpoint)

    return _factory


# To prevent concurrent writes
settings_write_lock = asyncio.Lock()
