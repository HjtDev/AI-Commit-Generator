from cli import app, console, err_console, __version__, APP_NAME
from typing import Optional
import typer
from cli import config
from cli.actions import run


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"{APP_NAME} {__version__}")
        raise typer.Exit()

@app.callback(invoke_without_command=True)
def main(
        ctx: typer.Context,
        hint: Optional[str] = typer.Option(
            None, "--hint", "-H", help="Extra context about the change to guide the model."
        ),
        yes: bool = typer.Option(
            False, "--yes", "-y", help="Commit immediately without the interactive prompt."
        ),
        unstaged: bool = typer.Option(
            False, "--unstaged", "-u", help="Use the unstaged diff instead of the staged one."
        ),
        no_stream: bool = typer.Option(
            False, "--no-stream", help="Wait for the full response instead of streaming tokens."
        ),
        dry_run: bool = typer.Option(
            False, "--dry-run", help="Generate and preview the message, but never commit."
        ),
        path: Optional[str] = typer.Option(
            None, "--path", "-p", help="Path to the git repository (defaults to the current directory)."
        ),
        max_chars: int = typer.Option(
            config.default_max_diff_chars, "--max-diff-chars", help="Truncate diffs larger than this many characters."
        ),
        model: Optional[str] = typer.Option(
            None, "--model", "-m", help="Override the configured model for this run only."
        ),
        endpoint: Optional[str] = typer.Option(
            None, "--endpoint", help="Override the configured provider endpoint for this run only."
        ),
        version: Optional[bool] = typer.Option(
            None, "--version", callback=_version_callback, is_eager=True, help="Show the version and exit."
        ),
) -> None:
    """
    Run with no subcommand to generate a commit message for your staged changes.
    """
    if ctx.invoked_subcommand is not None:
        return
    run(hint, yes, unstaged, no_stream, path, max_chars, model, endpoint, dry_run)


@app.command()
def serve(
        port: int = typer.Option(8000, "--port", help="Port to serve the Web UI on."),
        host: str = typer.Option("127.0.0.1", "--host", help="Host to bind the Web UI to."),
        open_browser: bool = typer.Option(False, "--open", help="Open the Web UI in your browser."),
) -> None:
    """Launch the FastAPI server + Web UI."""
    import uvicorn
    from ui.backend.main import app as fastapi_app

    if open_browser:
        import threading
        import time
        import webbrowser

        def _open():
            time.sleep(1)  # for uvicorn
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=_open, daemon=True).start()

    console.print(f"[bold cyan]Serving at[/bold cyan] http://{host}:{port}")
    uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")
