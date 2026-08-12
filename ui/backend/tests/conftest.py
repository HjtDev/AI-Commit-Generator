from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

from ui.backend import dependencies
from ui.backend.main import app


def run_git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A freshly-initialized git repo with a committer identity configured.

    Mirrors core/tests/test_git.py's fixture of the same name -- the backend
    tests exercise real `git` subprocess calls through the HTTP layer rather
    than mocking Git, matching how the rest of this project tests git
    behavior.
    """
    run_git("init", cwd=tmp_path)
    run_git("config", "user.email", "test@example.com", cwd=tmp_path)
    run_git("config", "user.name", "Test User", cwd=tmp_path)
    return tmp_path


@pytest.fixture
def repo_with_commit(repo: Path) -> Path:
    (repo / "file.txt").write_text("hello\n")
    run_git("add", "file.txt", cwd=repo)
    run_git("commit", "-m", "initial commit", cwd=repo)
    return repo


@pytest.fixture
def client() -> TestClient:
    """A TestClient with a clean dependency_overrides slate per test.

    Every test that overrides a dependency (config path, llm service
    factory, git factory) does so on this shared `app` object -- without
    resetting after each test, an override from one test would silently
    leak into the next.
    """
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def isolated_config_path(client: TestClient, tmp_path: Path) -> Path:
    """Points the settings router at a throwaway file for this test only.

    Without this, `get_config_path` defaults to the real project
    `core/config.json` -- exactly the file a bug during manual verification
    of this backend once overwrote with test data. Every settings test must
    use this fixture (or override `get_config_path` itself) rather than
    hitting `/settings` directly against the real `client` fixture.
    """
    path = tmp_path / "config.json"
    app.dependency_overrides[dependencies.get_config_path] = lambda: path
    return path
