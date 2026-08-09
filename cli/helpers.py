from rich.panel import Panel
from rich.text import Text
from cli import SYSTEM_PROMPT_PATH, err_console
from typing import Optional
from core.git import Git
from core.llm import LLMService
from core.settings import Config
import typer


def get_system_prompt() -> str:
    if SYSTEM_PROMPT_PATH.is_file():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    err_console.print(
        f"[yellow]⚠ No system prompt found at[/yellow] [dim]{SYSTEM_PROMPT_PATH}[/dim] "
        "[yellow]— continuing without one.[/yellow]"
    )
    return ""


def resolve_git(path: Optional[str]) -> Git:
    try:
        return Git(path)
    except RuntimeError as exc:
        err_console.print(f"[bold red]✗[/bold red] {exc}")
        raise typer.Exit(code=1)


def build_llm(config: Config, model: Optional[str], endpoint: Optional[str]) -> LLMService:
    return LLMService(
        endpoint=endpoint or config.endpoint,
        model=model or config.model,
        api_key=config.api_key or "AI-COMMIT",
        timeout=config.timeout,
        retries=config.retries,
        conventional=config.conventional,
        system_prompt=get_system_prompt(),
    )


def split_title_body(text: str) -> tuple[str, str]:
    lines = [ln for ln in text.splitlines()]
    # drop leading blank lines
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return "", ""
    title = lines[0].strip()
    body = "\n".join(lines[1:]).strip()
    return title, body


def render_message(title: str, body: str) -> Panel:
    content = Text(title, style="bold green")
    if body:
        content.append("\n\n")
        content.append(Text(body))
    return Panel(content, title="Generated Commit Message", border_style="cyan", expand=False)


def print_generation_error(exc: Exception, endpoint: str) -> None:
    if isinstance(exc, (ValueError,)) or "empty output" in str(exc).lower():
        err_console.print("[bold red]✗ The model responded, but returned an unusable message.[/bold red]")
        err_console.print(f"  [red]{exc}[/red]")
        err_console.print(
            "\n[yellow]Troubleshooting:[/yellow]\n"
            "  • The model may not be following the system prompt's fenced-block format.\n"
            "  • Try [bold]--no-stream[/bold], a different --model, or check core/docs/System-Prompt.md."
        )
        return

    err_console.print(f"[bold red]✗ Could not reach the model provider at[/bold red] [dim]{endpoint}[/dim]")
    err_console.print(f"  [red]{exc}[/red]")
    err_console.print(
        "\n[yellow]Troubleshooting:[/yellow]\n"
        "  • Is your provider's server actually running? "
        "(e.g. LM Studio's local server, or [bold]ollama serve[/bold])\n"
        "  • Does [bold]git-auto-commit config show[/bold] point at the right endpoint/model?\n"
        "  • If using a cloud API, check your API key and network connection."
    )
