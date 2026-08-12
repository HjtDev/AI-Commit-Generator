from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import ValidationError as PydanticValidationError
from core.settings import Config, mask_secret
from ..dependencies import get_config, get_config_path, settings_write_lock
from ..errors import APIError
from ..openapi import build_responses
from ..schemas.settings import SettingsResponse, SettingsUpdateRequest, SettingsRes

router = APIRouter(prefix="/settings", tags=["Settings"])


def _to_response(config: Config, spec) -> SettingsResponse:
    data = config.model_dump()
    data["api_key"] = mask_secret(data.get("api_key"))
    return SettingsResponse.from_spec(spec, **data)


@router.get(
    "",
    response_model=SettingsResponse,
    name="Get Settings",
    description="Get the current persisted configuration. `api_key` is masked.",
)
def get_settings(config: Config = Depends(get_config)):
    return _to_response(config, SettingsRes.SUCCESS_GET.value)


@router.patch(
    "",
    response_model=SettingsResponse,
    name="Update Settings",
    description="Partially update and persist the configuration.",
    responses=build_responses(SettingsRes.NO_FIELDS, SettingsRes.INVALID_VALUE),
)
async def update_settings(
        payload: SettingsUpdateRequest,
        config: Config = Depends(get_config),
        config_path: Path = Depends(get_config_path),
):
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise APIError(SettingsRes.NO_FIELDS)

    try:
        # Using dict union
        # Only grabs keys from the updates and merge it into current config
        # if the key already exists in the config
        updated = Config.model_validate(config.model_dump() | updates)
    except PydanticValidationError as e:
        raise APIError(SettingsRes.INVALID_VALUE, detail=str(e))

    async with settings_write_lock:
        updated.save(config_path)

    return _to_response(updated, SettingsRes.SUCCESS_UPDATE.value)


@router.post(
    "/reset",
    response_model=SettingsResponse,
    name="Reset Settings",
    description="Reset the configuration to its defaults.",
)
async def reset_settings(
        config: Config = Depends(get_config),
        config_path: Path = Depends(get_config_path),
):
    async with settings_write_lock:
        reset = config.reset_to_default(config_path)

    return _to_response(reset, SettingsRes.SUCCESS_RESET.value)
