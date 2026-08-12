from typing import Annotated, Callable

from fastapi import APIRouter, Depends, Query

from core.git import Git
from core.settings import Config
from ..dependencies import get_config, get_git_factory
from ..errors import APIError
from ..openapi import build_responses
from ..schemas.git import (
    GetDiffRequest,
    GetDiffSuccessResponse,
    CommitRequest,
    CommitSuccessResponse,
    GitRes,
)

router = APIRouter(prefix="/git", tags=["Git"])

GitFactory = Callable[..., Git]


@router.get(
    "/diff",
    response_model=GetDiffSuccessResponse,
    name="Get Diff",
    description="Get Git Diff with truncation option",
    responses=build_responses(
        GitRes.PATH_NOT_FOUND,
        GitRes.INVALID_REPO,
        GitRes.TRUNCATE_PARAMS,
        GitRes.GIT_COMMAND_FAILED,
        GitRes.NO_CHANGES,
    ),
)
def get_diff(
        query: Annotated[GetDiffRequest, Query()],
        config: Config = Depends(get_config),
        git_factory: GitFactory = Depends(get_git_factory),
):
    try:
        git = git_factory(query.path)
    except FileNotFoundError:
        raise APIError(GitRes.PATH_NOT_FOUND)
    except RuntimeError as e:
        # Raised from Git.__init__
        raise APIError(GitRes.INVALID_REPO, detail=str(e))

    max_diff_chars = (
        query.max_diff_chars if query.max_diff_chars is not None else config.default_max_diff_chars
    )

    try:
        diff = git.get_diff(staged=query.staged, truncate=query.truncate, max_diff_chars=max_diff_chars)
    except ValueError as e:
        raise APIError(GitRes.TRUNCATE_PARAMS, detail=str(e))
    except RuntimeError as e:
        # The `git diff` subprocess itself failed.
        raise APIError(GitRes.GIT_COMMAND_FAILED, detail=str(e))

    if not diff.strip():
        raise APIError(GitRes.NO_CHANGES)

    return GetDiffSuccessResponse.from_spec(GitRes.SUCCESS_DIFF.value, diff=diff)


@router.post(
    "/commit",
    response_model=CommitSuccessResponse,
    name="Git Commit",
    description="Commit the currently staged changes.",
    responses=build_responses(
        GitRes.PATH_NOT_FOUND,
        GitRes.INVALID_REPO,
        GitRes.NOTHING_STAGED,
    ),
)
def commit(
        payload: CommitRequest,
        git_factory: GitFactory = Depends(get_git_factory),
):
    try:
        git = git_factory(payload.path)
    except FileNotFoundError:
        raise APIError(GitRes.PATH_NOT_FOUND)
    except RuntimeError as e:
        raise APIError(GitRes.INVALID_REPO, detail=str(e))

    try:
        git.commit(message=payload.message, description=payload.description)
    except RuntimeError as e:
        raise APIError(GitRes.NOTHING_STAGED, detail=str(e))

    return CommitSuccessResponse.from_spec(GitRes.SUCCESS_COMMIT.value)
