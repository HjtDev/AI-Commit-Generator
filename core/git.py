import os, subprocess


class Git:
    def __init__(self, path: str | None = None):
        self.repo_path = path or os.getcwd()
        
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.repo_path, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Not a valid git repository at '{self.repo_path}'.\n{result.stderr}")

    def _run(self, *args: str) -> str:
        command = ["git", *args]
        result = subprocess.run(command, cwd=self.repo_path, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to execute '{' '.join(command)}':\n{result.stderr}")
        return result.stdout

    def get_diff(self, staged: bool = True, truncate: bool = False, max_diff_chars: int = -1) -> str:
        diff = self._run("diff", "--staged") if staged else self._run("diff")

        if truncate and max_diff_chars < 1:
            raise ValueError("If you want to truncate the diff you should pass a max_diff_chars greater than 1.")

        if truncate:
            diff, _ = self.truncate_diff(diff, max_diff_chars)

        return diff

    def commit(self, message: str, description: str = "") -> bool:
        args = ["commit", "-m", message]
        if description:
            args += ["-m", description]
        self._run(*args)
        return True

    @staticmethod
    def truncate_diff(diff: str, max_chars: int) -> tuple[str, bool]:
        if len(diff) <= max_chars:
            return diff, False

        lockfile_markers = (
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "uv.lock",
            "poetry.lock",
            "Cargo.lock",
            "Gemfile.lock",
            "composer.lock",
        )

        blocks = diff.split("\ndiff --git ")
        prioritized, deprioritized = [], []
        for i, block in enumerate(blocks):
            text = block if i == 0 else "diff --git " + block
            (deprioritized if any(m in text for m in lockfile_markers) else prioritized).append(text)

        ordered = prioritized + deprioritized
        kept, used = [], 0
        for block in ordered:
            if used + len(block) > max_chars:
                break
            kept.append(block)
            used += len(block)

        truncated_text = "\n".join(kept) if kept else diff[:max_chars]
        truncated_text += "\n\n[...diff truncated: exceeded max-diff-chars limit...]"
        return truncated_text, True
