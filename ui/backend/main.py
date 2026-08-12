from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .errors import register_exception_handlers
from .routers.git import router as git_router
from .routers.settings import router as settings_router
from .routers.llm import router as llm_router


def create_app() -> FastAPI:
    # DEBUG in the settings is separate from here
    fastapi_app = FastAPI(title=settings.app_name, version=settings.version)

    register_exception_handlers(fastapi_app)

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    fastapi_app.include_router(git_router)
    fastapi_app.include_router(settings_router)
    fastapi_app.include_router(llm_router)

    @fastapi_app.get("/health", tags=["Health"], name="Health Check")
    def health() -> dict:
        return {"status": "ok", "version": settings.version}

    return fastapi_app


app = create_app()
