from rich.table import Table
from typing import Optional
from cli import config_app, console, err_console
from core.settings import Config, CONFIG_FILE
import typer


@config_app.command("show")
def config_show() -> None:
    """Print the current configuration."""
    config = Config.load()
    table = Table(title="Current Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Key")
    table.add_column("Value")
    for field_name in type(config).model_fields:
        value = getattr(config, field_name)
        if field_name == "api_key" and value:
            value = value[:4] + "…" + value[-2:] if len(value) > 8 else "****"
        table.add_row(field_name, str(value))
    console.print(table)
    from core.settings import CONFIG_FILE

    console.print(f"[dim]Location: {CONFIG_FILE}[/dim]")


@config_app.command("path")
def config_path() -> None:
    """Print the path to the config file."""

    console.print(str(CONFIG_FILE))


@config_app.command("set")
def config_set(
        endpoint: Optional[str] = typer.Option(None, help="Provider base URL, e.g. http://localhost:1234/v1"),
        api_key: Optional[str] = typer.Option(None, help="API key (use 'AI-COMMIT' or blank for most local servers)"),
        model: Optional[str] = typer.Option(None, help="Model name/id to request from the provider"),
        conventional: Optional[bool] = typer.Option(
            None, help="Use lowercase Conventional Commit types instead of capitalized ones"
        ),
        auto_commit_on_success: Optional[bool] = typer.Option(
            None, help="Skip the interactive prompt and commit automatically whenever generation succeeds"
        ),
        timeout: Optional[int] = typer.Option(None, help="Request timeout in seconds"),
        retries: Optional[int] = typer.Option(None, help="Number of retries on request failure"),
) -> None:
    """Update and persist one or more configuration values."""
    config = Config.load()
    updates = {
        "endpoint": endpoint,
        "api_key": api_key,
        "model": model,
        "conventional": conventional,
        "auto_commit_on_success": auto_commit_on_success,
        "timeout": timeout,
        "retries": retries,
    }
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        err_console.print("[yellow]Nothing to update — pass at least one option.[/yellow]")
        raise typer.Exit(code=1)

    for key, value in updates.items():
        setattr(config, key, value)
    config.save()

    console.print("[bold green]✓ Configuration updated:[/bold green]")
    for key, value in updates.items():
        console.print(f"  [cyan]{key}[/cyan] = {value}")


@config_app.command("reset")
def config_reset(
        confirm: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Reset the configuration to its defaults."""
    if not confirm:
        proceed = typer.confirm("Reset configuration to defaults?")
        if not proceed:
            raise typer.Exit()
    config = Config.load()
    config.reset_to_default()
    console.print("[bold green]✓ Configuration reset to defaults.[/bold green]")
