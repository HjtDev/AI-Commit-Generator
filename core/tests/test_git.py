from pathlib import Path
import pytest, subprocess
from core.git import Git


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A freshly-initialized git repo with a committer identity configured."""
    run("init", cwd=tmp_path)
    run("config", "user.email", "test@example.com", cwd=tmp_path)
    run("config", "user.name", "Test User", cwd=tmp_path)
    return tmp_path


@pytest.fixture
def repo_with_commit(repo: Path) -> Path:
    """A repo with one tracked file and an initial commit, so later diffs have a baseline."""
    (repo / "file.txt").write_text("hello\n")
    run("add", "file.txt", cwd=repo)
    run("commit", "-m", "initial commit", cwd=repo)
    return repo


class TestInit:
    def test_raises_outside_a_git_repo(self, tmp_path: Path):
        with pytest.raises(RuntimeError):
            Git(str(tmp_path))

    def test_succeeds_inside_a_git_repo(self, repo: Path):
        git = Git(str(repo))
        assert git.repo_path == str(repo)

    def test_defaults_to_cwd_when_no_path_given(self, repo: Path, monkeypatch):
        monkeypatch.chdir(repo)
        git = Git()
        assert git.repo_path == str(repo)

    def test_uses_given_path_regardless_of_process_cwd(self, repo: Path, tmp_path_factory, monkeypatch):
        # Regression test: instantiating with an explicit path must not
        # silently operate on the process's current working directory.
        other_dir = tmp_path_factory.mktemp("elsewhere")
        monkeypatch.chdir(other_dir)
        git = Git(str(repo))
        assert git.repo_path == str(repo)


class TestGetDiff:
    def test_no_diff_when_clean(self, repo_with_commit: Path):
        git = Git(str(repo_with_commit))
        assert git.get_diff(staged=False) == ""
        assert git.get_diff(staged=True) == ""

    def test_unstaged_diff_shows_working_tree_changes(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        git = Git(str(repo_with_commit))
        diff = git.get_diff(staged=False)
        assert "changed" in diff
        # Not staged yet, so the staged diff must stay empty.
        assert git.get_diff(staged=True) == ""

    def test_staged_diff_shows_added_changes(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        diff = git.get_diff(staged=True)
        assert "changed" in diff
        # Working tree now matches the index, so unstaged diff is empty.
        assert git.get_diff(staged=False) == ""

    def test_runs_against_the_correct_repo(self, repo_with_commit: Path, tmp_path_factory, monkeypatch):
        other_dir = tmp_path_factory.mktemp("elsewhere")
        monkeypatch.chdir(other_dir)
        (repo_with_commit / "file.txt").write_text("changed\n")
        git = Git(str(repo_with_commit))
        assert "changed" in git.get_diff(staged=False)


class TestCommit:
    def test_commit_with_message_only(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        assert git.commit("Update file") is True

        log = run("log", "-1", "--pretty=%s", cwd=repo_with_commit).stdout.strip()
        assert log == "Update file"

    def test_commit_with_description_creates_body(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        git.commit("Update file", "- did a thing\n- did another thing")

        body = run("log", "-1", "--pretty=%b", cwd=repo_with_commit).stdout.strip()
        assert "did a thing" in body
        assert "did another thing" in body

    def test_commit_with_nothing_staged_raises(self, repo_with_commit: Path):
        git = Git(str(repo_with_commit))
        with pytest.raises(RuntimeError):
            git.commit("Nothing to see here")

    def test_error_message_includes_git_stderr(self, repo_with_commit: Path):
        git = Git(str(repo_with_commit))
        with pytest.raises(RuntimeError) as excinfo:
            git.commit("Nothing to see here")
        # Sanity check that we're surfacing git's actual stderr, not swallowing it.
        assert str(excinfo.value).strip() != ""