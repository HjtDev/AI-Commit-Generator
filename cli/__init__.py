from core.settings import Config
from pathlib import Path
from rich.console import Console
import typer


APP_NAME = "git-auto-commit"
__version__ = "0.4.0"

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "core" / "docs" / "System-Prompt.md"

config = Config.load()

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(
    name=APP_NAME,
    help="Generate semantic commit messages from your staged changes using a local or cloud LLM.",
    add_completion=True,
    no_args_is_help=False,
    rich_markup_mode="rich",
)

config_app = typer.Typer(help="View or update the persisted configuration.")
app.add_typer(config_app, name="config")
