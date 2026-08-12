from pathlib import Path

from fastapi.testclient import TestClient

from .conftest import run_git


class TestGetDiff:
    def test_no_changes_returns_404(self, client: TestClient, repo_with_commit: Path):
        r = client.get("/git/diff", params={"path": str(repo_with_commit)})
        assert r.status_code == 404
        body = r.json()
        assert body["success"] is False
        assert body["err_code"] == 104

    def test_staged_diff_returns_200_with_diff_text(self, client: TestClient, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("changed\n")
        run_git("add", "file.txt", cwd=repo_with_commit)

        r = client.get("/git/diff", params={"path": str(repo_with_commit)})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["err_code"] == 0
        assert "changed" in body["diff"]

    def test_unstaged_diff(self, client: TestClient, repo_with_commit: Path):
        (repo_with_commit / "file.txt").write_text("unstaged change\n")

        r = client.get("/git/diff", params={"path": str(repo_with_commit), "staged": False})
        assert r.status_code == 200
        assert "unstaged change" in r.json()["diff"]

        # Staged diff must stay empty since nothing was `git add`ed.
        staged = client.get("/git/diff", params={"path": str(repo_with_commit), "staged": True})
        assert staged.status_code == 404

    def test_omitting_max_diff_chars_uses_server_default_without_erroring(
            self, client: TestClient, repo_with_commit: Path
    ):
        # truncate defaults to True; max_diff_chars defaults to None, which
        # the router falls back to config.default_max_diff_chars (128000).
        # A small real diff must NOT trip the "explicit truncate needs an
        # explicit max_diff_chars" guard just because the caller omitted it.
        (repo_with_commit / "file.txt").write_text("small change\n")
        run_git("add", "file.txt", cwd=repo_with_commit)

        r = client.get("/git/diff", params={"path": str(repo_with_commit)})
        assert r.status_code == 200
        assert "[...diff truncated" not in r.json()["diff"]


class TestGetDiffErrors:
    def test_bad_path_returns_400_path_not_found(self, client: TestClient):
        r = client.get("/git/diff", params={"path": "/no/such/directory/at/all"})
        assert r.status_code == 400
        assert r.json()["err_code"] == 105

    def test_not_a_repo_returns_400_invalid_repo(self, client: TestClient, tmp_path: Path):
        r = client.get("/git/diff", params={"path": str(tmp_path)})
        assert r.status_code == 400
        assert r.json()["err_code"] == 101

    def test_explicit_truncate_with_unset_max_chars_returns_400(
            self, client: TestClient, repo_with_commit: Path
    ):
        r = client.get(
            "/git/diff",
            params={"path": str(repo_with_commit), "truncate": True, "max_diff_chars": -1},
        )
        assert r.status_code == 400
        assert r.json()["err_code"] == 103


class TestCommit:
    def test_commit_via_json_body(self, client: TestClient, repo_with_commit: Path):
        # Regression test: /git/commit originally accepted `path`/`message`/
        # `description` as silently-required QUERY params despite the
        # CommitRequest schema promising a JSON body. This is the shape a
        # real client (or the OpenAPI docs) expects to work.
        (repo_with_commit / "file.txt").write_text("changed\n")
        run_git("add", "file.txt", cwd=repo_with_commit)

        r = client.post(
            "/git/commit",
            json={"path": str(repo_with_commit), "message": "Update file", "description": "- did a thing"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert body["err_code"] == 0

        log = run_git("log", "-1", "--pretty=%s", cwd=repo_with_commit).stdout.strip()
        assert log == "Update file"
        body_text = run_git("log", "-1", "--pretty=%b", cwd=repo_with_commit).stdout.strip()
        assert "did a thing" in body_text

    def test_commit_via_query_params_now_rejected(self, client: TestClient, repo_with_commit: Path):
        # The inverse of the above: the old (broken) calling convention must
        # no longer be accepted, since it's not what CommitRequest declares.
        (repo_with_commit / "file.txt").write_text("changed\n")
        run_git("add", "file.txt", cwd=repo_with_commit)

        r = client.post(
            "/git/commit",
            params={"path": str(repo_with_commit), "message": "Update file"},
        )
        assert r.status_code == 422


class TestCommitErrors:
    def test_nothing_staged_returns_409(self, client: TestClient, repo_with_commit: Path):
        r = client.post("/git/commit", json={"path": str(repo_with_commit), "message": "Nothing to commit"})
        assert r.status_code == 409
        assert r.json()["err_code"] == 106

    def test_bad_path_returns_400_path_not_found(self, client: TestClient):
        r = client.post("/git/commit", json={"path": "/no/such/directory/at/all", "message": "x"})
        assert r.status_code == 400
        assert r.json()["err_code"] == 105

    def test_not_a_repo_returns_400_invalid_repo(self, client: TestClient, tmp_path: Path):
        r = client.post("/git/commit", json={"path": str(tmp_path), "message": "x"})
        assert r.status_code == 400
        assert r.json()["err_code"] == 101


class TestOpenAPIDocs:
    def test_diff_400_documents_every_distinct_cause(self, client: TestClient):
        # Regression test for the original bug: PATH_NOT_FOUND and
        # TRUNCATE_PARAMS both return 400, but only one was documented.
        # build_responses() must surface every cause sharing that status
        # code as its own named example.
        schema = client.app.openapi()
        four_hundred = schema["paths"]["/git/diff"]["get"]["responses"]["400"]
        examples = four_hundred["content"]["application/json"]["examples"]
        assert "GitRes.PATH_NOT_FOUND" in examples
        assert "GitRes.TRUNCATE_PARAMS" in examples
        assert "GitRes.INVALID_REPO" in examples
        assert examples["GitRes.PATH_NOT_FOUND"]["value"]["err_code"] != examples["GitRes.TRUNCATE_PARAMS"]["value"]["err_code"]
