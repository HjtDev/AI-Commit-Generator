import json
from pathlib import Path

from fastapi.testclient import TestClient

from core.settings import CONFIG_FILE


class TestGetSettings:
    def test_creates_default_file_and_returns_defaults(
            self, client: TestClient, isolated_config_path: Path
    ):
        assert not isolated_config_path.exists()

        r = client.get("/settings")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["model"] == "qwen2.5-coder-3b-instruct"
        assert body["api_key"] is None
        assert isolated_config_path.exists()


class TestPatchSettings:
    def test_update_persists_and_is_visible_on_next_get(
            self, client: TestClient, isolated_config_path: Path
    ):
        # This is also the regression test for the load/save path-coupling
        # bug found during manual verification: Config.load(path)/.save(path)
        # don't remember each other, so a router that loaded from one path
        # but saved via a bare .save() would silently write the real
        # on-disk config regardless of what was loaded. If GET after PATCH
        # doesn't reflect the update, load and save disagreed about the path.
        r = client.patch("/settings", json={"model": "new-model", "timeout": 99})
        assert r.status_code == 200
        assert r.json()["model"] == "new-model"
        assert r.json()["timeout"] == 99

        r = client.get("/settings")
        assert r.json()["model"] == "new-model"
        assert r.json()["timeout"] == 99

    def test_api_key_is_masked_in_response_but_not_on_disk(
            self, client: TestClient, isolated_config_path: Path
    ):
        r = client.patch("/settings", json={"api_key": "sk-1234567890abcdef"})
        assert r.status_code == 200
        assert r.json()["api_key"] == "sk-1…ef"

        disk = json.loads(isolated_config_path.read_text())
        assert disk["api_key"] == "sk-1234567890abcdef"

    def test_empty_body_returns_400(self, client: TestClient, isolated_config_path: Path):
        r = client.patch("/settings", json={})
        assert r.status_code == 400
        assert r.json()["err_code"] == 301

    def test_bad_type_returns_422(self, client: TestClient, isolated_config_path: Path):
        r = client.patch("/settings", json={"timeout": "not-an-int"})
        assert r.status_code == 422

    def test_unset_fields_are_left_untouched(self, client: TestClient, isolated_config_path: Path):
        client.patch("/settings", json={"model": "keep-me"})
        r = client.patch("/settings", json={"timeout": 45})
        assert r.status_code == 200
        assert r.json()["model"] == "keep-me"
        assert r.json()["timeout"] == 45

    def test_does_not_touch_the_real_project_config(
            self, client: TestClient, isolated_config_path: Path
    ):
        before = CONFIG_FILE.read_text() if CONFIG_FILE.exists() else None

        client.patch("/settings", json={"model": "should-never-reach-real-config"})

        after = CONFIG_FILE.read_text() if CONFIG_FILE.exists() else None
        assert before == after


class TestResetSettings:
    def test_reset_restores_defaults_and_persists(
            self, client: TestClient, isolated_config_path: Path
    ):
        client.patch("/settings", json={"model": "temporary-model"})

        r = client.post("/settings/reset")
        assert r.status_code == 200
        assert r.json()["model"] == "qwen2.5-coder-3b-instruct"

        # Persisted, not just returned in the response -- reset_to_default()
        # returns a NEW instance and the router must use that return value
        # rather than the (unmutated) instance it was called on.
        r = client.get("/settings")
        assert r.json()["model"] == "qwen2.5-coder-3b-instruct"
