from enum import Enum, unique
from typing import Optional

from pydantic import BaseModel

from ui.backend.schemas.base import BaseResponse, ResponseSpec


class GenerateRequest(BaseModel):
    # The diff is passed in directly (e.g. from a prior GET /git/diff call)
    # rather than fetched here from a `path` -- keeps this router free of
    # any Git/subprocess dependency, and lets a caller show/let the user
    # edit the diff before generating.
    diff: str
    hint: str = ""
    model: Optional[str] = None
    endpoint: Optional[str] = None


class GenerateSuccessResponse(BaseResponse):
    title: str
    body: str


@unique
class LlmRes(Enum):
    SUCCESS = ResponseSpec(message="Success", code=0, http_status=200)
    EMPTY_DIFF = ResponseSpec(message="diff must not be empty.", code=201, http_status=400)
    ENDPOINT_UNREACHABLE = ResponseSpec(
        message="Could not reach the model provider.", code=202, http_status=502
    )
    AUTH_FAILED = ResponseSpec(
        message="The model provider rejected the API key.", code=203, http_status=502
    )
    PROVIDER_ERROR = ResponseSpec(
        message="The model provider returned an error.", code=204, http_status=502
    )
    UNUSABLE_OUTPUT = ResponseSpec(
        message="The model responded, but returned an unusable message.",
        code=205,
        http_status=502,
    )
