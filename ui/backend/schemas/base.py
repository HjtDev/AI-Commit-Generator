from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ResponseSpec(BaseModel):
    """The value held by each member of a domain's `*Res` enum.

    Ties a canned message, a stable numeric code, and the HTTP status that
    should accompany it into one place, so a router raises/documents a single
    object instead of keeping message/code/status in sync by hand across the
    raise site, the response body, and the OpenAPI docs.
    """

    model_config = ConfigDict(frozen=True)

    message: str
    code: int
    http_status: int

    @field_validator("http_status")
    @classmethod
    def _valid_http_status(cls, v: int) -> int:
        if not (100 <= v <= 599):
            raise ValueError("http_status must be a valid HTTP status code (100-599)")
        return v


class BaseResponse(BaseModel):
    success: bool
    message: str
    err_code: int

    @classmethod
    def from_spec(cls, spec: ResponseSpec, **extra) -> BaseResponse:
        return cls(success=True, message=spec.message, err_code=spec.code, **extra)


class ErrorResponse(BaseResponse):
    # Raw exception text (e.g. git stderr), which can carry absolute paths or
    # credential-bearing URLs. Only ever populated when the app runs in debug
    # mode — see errors.py. `message` stays the stable, docs-truthful string
    # from the ResponseSpec regardless.
    detail: Optional[str] = None

    @classmethod
    def from_spec(cls, spec: ResponseSpec, detail: Optional[str] = None) -> ErrorResponse:
        return cls(success=False, message=spec.message, err_code=spec.code, detail=detail)
