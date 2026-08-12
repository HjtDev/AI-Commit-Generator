from __future__ import annotations
from enum import Enum
from typing import Optional, Union
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from .schemas.base import ErrorResponse, ResponseSpec

# Generic, non-domain-specific specs. Deliberately NOT part of any domain
# `*Res` enum -- these are raised by the framework/handlers themselves, never
# by router code, so there's no per-domain duplication risk for them.
VALIDATION_SPEC = ResponseSpec(message="Request validation failed.", code=-1, http_status=422)
INTERNAL_SPEC = ResponseSpec(message="Internal Server Error.", code=-2, http_status=500)


class APIError(Exception):
    """Raise this from a router to produce a documented error response.

    Accepts either a bare `ResponseSpec` or an `*Res` enum member (e.g.
    `GitRes.NOT_A_REPO`) -- the same enum members already passed to
    `build_responses(...)`, so a call site never has to remember to unwrap
    `.value` to match one call and not the other.

    `detail`, when given, is the raw underlying text (e.g. git stderr) -- it
    is only ever surfaced to the client when the app runs in debug mode.
    """

    def __init__(self, spec: Union[ResponseSpec, Enum], detail: Optional[str] = None):
        self.spec: ResponseSpec = spec.value if isinstance(spec, Enum) else spec
        self.detail = detail
        super().__init__(self.spec.message)


def _debug_enabled() -> bool:
    # Local import avoids a hard import-time dependency between errors.py and config.py
    from .config import settings

    return settings.debug


async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    body = ErrorResponse.from_spec(exc.spec, detail=exc.detail if _debug_enabled() else None)
    return JSONResponse(status_code=exc.spec.http_status, content=body.model_dump())


async def _request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    body = ErrorResponse.from_spec(
        VALIDATION_SPEC, detail=str(exc.errors()) if _debug_enabled() else None
    )
    return JSONResponse(status_code=VALIDATION_SPEC.http_status, content=body.model_dump())


async def _pydantic_validation_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
    # Distinct from RequestValidationError: raised when *our* code calls
    # Config.model_validate(...)/similar directly, not by FastAPI's own
    # request-parsing layer. Both should look identical to the client.
    body = ErrorResponse.from_spec(
        VALIDATION_SPEC, detail=str(exc.errors()) if _debug_enabled() else None
    )
    return JSONResponse(status_code=VALIDATION_SPEC.http_status, content=body.model_dump())


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    body = ErrorResponse.from_spec(INTERNAL_SPEC, detail=str(exc) if _debug_enabled() else None)
    return JSONResponse(status_code=INTERNAL_SPEC.http_status, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Wire up every handler in one call from `create_app()`.

    A function rather than module-level `@app.exception_handler(...)`
    decorators on purpose: the decorator form requires this module to import
    `app` from `main.py`, which imports the routers, which import this
    module -- a circular import. Calling this from `create_app()` instead
    keeps the dependency graph a DAG.
    """
    app.add_exception_handler(APIError, _api_error_handler)
    app.add_exception_handler(RequestValidationError, _request_validation_handler)
    app.add_exception_handler(PydanticValidationError, _pydantic_validation_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
