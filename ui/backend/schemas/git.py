from enum import Enum, unique
from typing import Optional
from pydantic import BaseModel
from ui.backend.schemas.base import BaseResponse, ResponseSpec


class GetDiffRequest(BaseModel):
    path: str
    staged: bool = True
    truncate: bool = True
    max_diff_chars: Optional[int] = None


class GetDiffSuccessResponse(BaseResponse):
    diff: str


class CommitRequest(BaseModel):
    path: str
    message: str
    description: str = ""


class CommitSuccessResponse(BaseResponse):
    pass


@unique
class GitRes(Enum):

    SUCCESS_DIFF = ResponseSpec(message="Success", code=0, http_status=200)
    SUCCESS_COMMIT = ResponseSpec(
        message="Successfully committed the staged files.", code=0, http_status=200
    )
    INVALID_REPO = ResponseSpec(message="Invalid repo", code=101, http_status=400)
    GIT_COMMAND_FAILED = ResponseSpec(message="Git command failed", code=102, http_status=500)
    TRUNCATE_PARAMS = ResponseSpec(message="Truncate params error", code=103, http_status=400)
    NO_CHANGES = ResponseSpec(
        message="No staged/unstaged changes found.", code=104, http_status=404
    )
    PATH_NOT_FOUND = ResponseSpec(message="Path not found", code=105, http_status=400)
    NOTHING_STAGED = ResponseSpec(
        message="Nothing staged to commit, or the commit itself failed.",
        code=106,
        http_status=409,
    )
