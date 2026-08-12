from enum import Enum, unique
from typing import Optional

from pydantic import BaseModel

from ui.backend.schemas.base import BaseResponse, ResponseSpec


class SettingsResponse(BaseResponse):
    endpoint: str
    api_key: Optional[str] = None  # masked -- see core.settings.mask_secret; never the raw key
    model: str
    conventional: bool
    auto_commit_on_success: bool
    timeout: int
    retries: int
    default_max_diff_chars: int


class SettingsUpdateRequest(BaseModel):
    """All-optional partial update -- mirrors `cli config set`'s options.
    Fields left unset (not merely `null`) are left untouched.
    """

    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    conventional: Optional[bool] = None
    auto_commit_on_success: Optional[bool] = None
    timeout: Optional[int] = None
    retries: Optional[int] = None
    default_max_diff_chars: Optional[int] = None


@unique
class SettingsRes(Enum):
    SUCCESS_GET = ResponseSpec(message="Success", code=0, http_status=200)
    SUCCESS_UPDATE = ResponseSpec(message="Configuration updated.", code=0, http_status=200)
    SUCCESS_RESET = ResponseSpec(message="Configuration reset to defaults.", code=0, http_status=200)
    NO_FIELDS = ResponseSpec(
        message="Nothing to update -- provide at least one field.", code=301, http_status=400
    )
    INVALID_VALUE = ResponseSpec(
        message="One or more values failed validation.", code=302, http_status=422
    )
