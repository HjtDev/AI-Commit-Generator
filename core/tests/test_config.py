from pathlib import Path
from pydantic import ValidationError
from core.settings import Config, mask_secret
import json, pytest


@pytest.fixture
def custom_config_path(tmp_path: Path) -> Path:
    """Provides a temporary non-existent config JSON path."""
    return tmp_path / "config.json"


@pytest.fixture
def existing_config_file(tmp_path: Path) -> Path:
    """Creates a pre-populated config.json with custom non-default values."""
    file_path = tmp_path / "custom_config.json"
    data = {
        "endpoint": "http://192.168.1.50:8080",
        "api_key": "secret-test-key",
        "model": "qwen2.5-coder-7b-instruct",
        "conventional": False,
        "auto_commit_on_success": True,
    }
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return file_path


class TestConfigLoad:
    def test_creates_default_config_file_if_missing(self, custom_config_path: Path):
        assert not custom_config_path.exists()

        config = Config.load(custom_config_path)

        # File should be created automatically on load
        assert custom_config_path.exists()
        assert config.endpoint == "127.0.0.1:1234"
        assert config.api_key is None
        assert config.model == "qwen2.5-coder-3b-instruct"
        assert config.conventional is True
        assert config.auto_commit_on_success is False

    def test_loads_existing_config_file(self, existing_config_file: Path):
        config = Config.load(existing_config_file)

        assert config.endpoint == "http://192.168.1.50:8080"
        assert config.api_key == "secret-test-key"
        assert config.model == "qwen2.5-coder-7b-instruct"
        assert config.conventional is False
        assert config.auto_commit_on_success is True

    def test_ignores_extra_unknown_keys_in_json(self, tmp_path: Path):
        file_path = tmp_path / "config_with_extra.json"
        data = {
            "endpoint": "127.0.0.1:1234",
            "model": "custom-model",
            "unknown_future_field": "some_value",
        }
        file_path.write_text(json.dumps(data), encoding="utf-8")

        config = Config.load(file_path)
        assert config.model == "custom-model"
        assert not hasattr(config, "unknown_future_field")

    def test_falls_back_to_default_if_json_is_corrupted(self, tmp_path: Path):
        file_path = tmp_path / "corrupt.json"
        file_path.write_text("invalid json contents {{{", encoding="utf-8")

        config = Config.load(file_path)
        assert config.endpoint == "127.0.0.1:1234"


class TestConfigEnvOverrides:
    def test_env_vars_override_json_and_defaults(
        self, custom_config_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("AI_COMMIT_ENDPOINT", "http://env-override:9000")
        monkeypatch.setenv("AI_COMMIT_API_KEY", "env-api-key")

        config = Config.load(custom_config_path)

        assert config.endpoint == "http://env-override:9000"
        assert config.api_key == "env-api-key"


class TestConfigSaveAndReset:
    def test_save_updates_file_on_disk(self, custom_config_path: Path):
        config = Config.load(custom_config_path)
        config.model = "qwen2.5-coder-14b-instruct"
        config.auto_commit_on_success = True
        config.save(custom_config_path)

        # Read directly from disk to verify persistence
        data = json.loads(custom_config_path.read_text(encoding="utf-8"))
        assert data["model"] == "qwen2.5-coder-14b-instruct"
        assert data["auto_commit_on_success"] is True

    def test_reset_to_default_overwrites_file(self, existing_config_file: Path):
        config = Config.load(existing_config_file)
        assert config.model == "qwen2.5-coder-7b-instruct"

        reset_config = config.reset_to_default(existing_config_file)

        assert reset_config.model == "qwen2.5-coder-3b-instruct"
        assert reset_config.conventional is True

        # Verify disk contents were reset as well
        disk_data = json.loads(existing_config_file.read_text(encoding="utf-8"))
        assert disk_data["model"] == "qwen2.5-coder-3b-instruct"


class TestConfigValidation:
    def test_raises_validation_error_on_invalid_type(self):
        with pytest.raises(ValidationError):
            Config(conventional="not_a_boolean")  # type: ignore


class TestMaskSecret:
    def test_none_returns_none(self):
        assert mask_secret(None) is None

    def test_empty_string_returns_empty_string(self):
        assert mask_secret("") == ""

    def test_short_value_returns_asterisks(self):
        assert mask_secret("12345678") == "****"

    def test_long_value_keeps_first_four_and_last_two(self):
        assert mask_secret("sk-1234567890abcdef") == "sk-1…ef"

    def test_never_returns_the_raw_value_for_a_realistic_key(self):
        raw = "sk-proj-abcdefghijklmnopqrstuvwxyz"
        masked = mask_secret(raw)
        assert masked != raw
        assert raw[4:-2] not in masked