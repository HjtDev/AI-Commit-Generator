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

    def get_diff(self, staged: bool = True) -> str:
        return self._run("diff", "--staged") if staged else self._run("diff")

    def commit(self, message: str, description: str = "") -> bool:
        args = ["commit", "-m", message]
        if description:
            args += ["-m", description]
        self._run(*args)
        return True
