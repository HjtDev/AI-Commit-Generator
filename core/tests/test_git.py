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


class TestGetDiffTruncation:
    """get_diff's truncate/max_diff_chars params, layered on top of a real repo."""

    def test_truncate_defaults_to_off(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("z" * 5000 + "\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        diff = git.get_diff(staged=True)
        assert "[...diff truncated" not in diff
        assert len(diff) > 1000

    def test_truncate_false_ignores_max_diff_chars_entirely(self, repo_with_commit: Path):
        # Even an otherwise-invalid max_diff_chars must be silently ignored
        # when truncate=False -- the guard only applies when truncation is requested.
        (repo_with_commit / "file.txt").write_text("z" * 5000 + "\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        diff = git.get_diff(staged=True, truncate=False, max_diff_chars=-1)
        assert "[...diff truncated" not in diff
        assert len(diff) > 1000

    def test_truncate_true_with_default_max_chars_raises(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        with pytest.raises(ValueError):
            git.get_diff(staged=True, truncate=True)

    def test_truncate_true_with_zero_max_chars_raises(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        with pytest.raises(ValueError):
            git.get_diff(staged=True, truncate=True, max_diff_chars=0)

    def test_truncate_true_with_negative_max_chars_raises(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        with pytest.raises(ValueError):
            git.get_diff(staged=True, truncate=True, max_diff_chars=-5)

    def test_truncate_true_with_boundary_value_one_does_not_raise(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        diff = git.get_diff(staged=True, truncate=True, max_diff_chars=1)
        assert isinstance(diff, str)

    def test_truncate_true_shrinks_large_diff_and_adds_marker(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("z" * 5000 + "\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        diff = git.get_diff(staged=True, truncate=True, max_diff_chars=200)
        assert "[...diff truncated: exceeded max-diff-chars limit...]" in diff
        # The kept portion (everything before the marker) must actually respect the limit.
        marker = "\n\n[...diff truncated: exceeded max-diff-chars limit...]"
        kept_portion = diff[: -len(marker)]
        assert len(kept_portion) <= 200

    def test_truncate_true_with_small_diff_leaves_it_unchanged(self, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run("add", "file.txt", cwd=repo_with_commit)
        git = Git(str(repo_with_commit))
        diff = git.get_diff(staged=True, truncate=True, max_diff_chars=100_000)
        assert "[...diff truncated" not in diff
        assert "changed" in diff


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


class TestTruncateDiffStatic:
    """Direct tests of Git.truncate_diff() as a pure function.

    Synthetic diff text (rather than real git output) is used here so the
    lockfile-deprioritization and length math can be pinned to exact,
    predictable byte counts.
    """

    APP_BLOCK = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -1,3 +1,4 @@\n"
            "+" + ("a" * 40) + "\n"
    )
    LOCK1_BLOCK = (
            "diff --git a/package-lock.json b/package-lock.json\n"
            "--- a/package-lock.json\n"
            "+++ b/package-lock.json\n"
            "@@ -1,3 +1,4 @@\n"
            "+" + ("b" * 40) + "\n"
    )
    LOCK2_BLOCK = (
            "diff --git a/yarn.lock b/yarn.lock\n"
            "--- a/yarn.lock\n"
            "+++ b/yarn.lock\n"
            "@@ -1,3 +1,4 @@\n"
            "+" + ("c" * 40) + "\n"
    )

    def test_returns_unchanged_when_under_limit(self):
        diff = "a small diff that easily fits"
        result, truncated = Git.truncate_diff(diff, 1000)
        assert result == diff
        assert truncated is False

    def test_returns_unchanged_at_exact_boundary(self):
        diff = "x" * 50
        result, truncated = Git.truncate_diff(diff, 50)
        assert result == diff
        assert truncated is False

    def test_truncates_and_flags_when_over_limit(self):
        diff = "x" * 100
        result, truncated = Git.truncate_diff(diff, 50)
        assert truncated is True
        assert result.endswith("[...diff truncated: exceeded max-diff-chars limit...]")

    def test_prioritizes_non_lockfile_block_even_when_it_comes_last(self):
        # Lockfile appears FIRST in the raw diff, the real source change LAST --
        # only room for one block, and it must be the source change, not the lockfile.
        combined = self.LOCK1_BLOCK + self.APP_BLOCK
        max_chars = len(self.APP_BLOCK) + 5
        assert max_chars < len(combined)  # sanity: truncation must actually trigger

        result, truncated = Git.truncate_diff(combined, max_chars)

        assert truncated is True
        assert "app.py" in result
        assert "package-lock.json" not in result

    def test_lockfile_block_kept_if_room_remains_after_priority_blocks(self):
        # Two lockfiles + one real change. Budget fits the real change plus
        # exactly one of the two lockfiles.
        combined = self.LOCK1_BLOCK + self.LOCK2_BLOCK + self.APP_BLOCK
        max_chars = len(self.APP_BLOCK) + len(self.LOCK1_BLOCK) + 2
        assert max_chars < len(combined)

        result, truncated = Git.truncate_diff(combined, max_chars)

        assert truncated is True
        assert "app.py" in result
        assert "package-lock.json" in result
        assert "yarn.lock" not in result
        # And the real change must be reordered ahead of the lockfile in the output,
        # even though it appeared last in the original diff.
        assert result.index("app.py") < result.index("package-lock.json")

    def test_falls_back_to_hard_slice_when_even_the_first_block_is_too_big(self):
        huge_block = "diff --git a/big.py b/big.py\n" + ("x" * 500)
        max_chars = 50

        result, truncated = Git.truncate_diff(huge_block, max_chars)

        assert truncated is True
        assert result.startswith(huge_block[:max_chars])
        assert result.endswith("[...diff truncated: exceeded max-diff-chars limit...]")

    def test_handles_diff_text_with_no_git_style_headers_as_a_single_block(self):
        # A raw unified diff with no "diff --git" markers at all should still
        # be truncated safely rather than erroring out.
        diff = ("--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n") * 20
        max_chars = 30

        result, truncated = Git.truncate_diff(diff, max_chars)

        assert truncated is True
        assert result.endswith("[...diff truncated: exceeded max-diff-chars limit...]")
        assert len(result) < len(diff)
