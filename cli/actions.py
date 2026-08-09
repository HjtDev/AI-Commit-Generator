from pathlib import Path
from typing import Optional
from rich.prompt import Prompt
from cli import err_console, console, config
from cli.helpers import resolve_git, build_llm, print_generation_error, render_message, split_title_body
from core.llm import LLMService
from core.git import Git
import asyncio
import os
import subprocess
import tempfile
import typer


def copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return True
    except Exception:
        pass

    # Deliberately not pre-checked with shutil.which(): on WSL / Windows with
    # Python < 3.12, os.access() misreports the executable bit for files on
    # the DrvFs-mounted Windows filesystem, so which() can return None for a
    # command (e.g. clip.exe) that actually runs fine. Trying it directly and
    # catching the failure is more reliable than probing availability first.
    candidates = (
        ["pbcopy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["clip.exe"],
        ["clip"],
    )
    for cmd in candidates:
        try:
            subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (OSError, subprocess.CalledProcessError):
            continue
    return False


def open_in_editor(initial_text: str) -> str:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or (
        "notepad" if os.name == "nt" else "nano"
    )
    with tempfile.NamedTemporaryFile(
            mode="w", suffix=".COMMIT_EDITMSG", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(initial_text)
        tmp_path = tmp.name
    try:
        subprocess.run([editor, tmp_path], check=True)
        return Path(tmp_path).read_text(encoding="utf-8")
    except Exception as exc:
        err_console.print(f"[bold red]✗ Failed to open editor '{editor}':[/bold red] {exc}")
        return initial_text
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def _generate(
        llm: LLMService, diff: str, hint: str, no_stream: bool
) -> tuple[str, str]:
    if no_stream:
        with console.status("[cyan]Generating commit message...[/cyan]", spinner="dots"):
            return await llm.generate(diff, hint)

    console.print("[dim]streaming from model...[/dim]\n")
    buffer = ""
    async for chunk in llm.stream(diff, hint):
        buffer += chunk
        console.print(chunk, end="")
    console.print("\n")
    return LLMService.parse_commit_output(buffer)


def run(
        hint: Optional[str],
        yes: bool,
        unstaged: bool,
        no_stream: bool,
        path: Optional[str],
        max_chars: int,
        model: Optional[str],
        endpoint: Optional[str],
        dry_run: bool,
) -> None:
    git = resolve_git(path)

    diff = git.get_diff(staged=not unstaged)
    if not diff.strip():
        source = "unstaged" if unstaged else "staged"
        err_console.print(f"[yellow]No {source} changes detected.[/yellow]")
        if not unstaged:
            err_console.print("Run [bold]git add <files>[/bold] first, or pass [bold]--unstaged[/bold].")
        raise typer.Exit(code=1)

    diff_text, was_truncated = Git.truncate_diff(diff, max_chars)
    if was_truncated:
        console.print(
            f"[yellow]⚠ Diff exceeded {max_chars} chars and was truncated "
            f"(lockfiles deprioritized first).[/yellow]"
        )

    llm = build_llm(config, model, endpoint)

    def generate_message() -> tuple[str, str]:
        try:
            new_title, new_body = asyncio.run(_generate(llm, diff_text, hint or "", no_stream))
        except Exception as exc:
            print_generation_error(exc, llm.endpoint)
            raise typer.Exit(code=1)
        if not new_title:
            err_console.print("[bold red]✗ Model returned an empty commit message.[/bold red]")
            raise typer.Exit(code=1)
        return new_title, new_body

    title, body = generate_message()
    console.print(render_message(title, body))

    if dry_run:
        console.print("[dim](dry run — nothing committed)[/dim]")
        return

    if yes or config.auto_commit_on_success:
        git.commit(title, body)
        console.print(f"[bold green]✓ Committed:[/bold green] {title}")
        return

    while True:
        choice = Prompt.ask(
            "\n[bold cyan][Y][/bold cyan]es commit  "
            "[bold cyan][E][/bold cyan]dit  "
            "[bold cyan][C][/bold cyan]opy ([bold cyan]ct[/bold cyan]=title, [bold cyan]cb[/bold cyan]=body)  "
            "[bold cyan][R][/bold cyan]etry  "
            "[bold cyan][N][/bold cyan]o abort",
            choices=["y", "e", "c", "ct", "cb", "r", "n"],
            default="y",
            show_choices=False,
        )

        if choice == "y":
            git.commit(title, body)
            console.print(f"[bold green]✓ Committed:[/bold green] {title}")
            break

        elif choice == "e":
            edited = open_in_editor(f"{title}\n\n{body}" if body else title)
            title, body = split_title_body(edited)
            if not title:
                err_console.print("[bold red]✗ Empty title after edit — aborting.[/bold red]")
                raise typer.Exit(code=1)
            console.print(render_message(title, body))
            continue

        elif choice.startswith("c"):
            text = f"{title}\n\n{body}" if body else title
            match choice[-1]:
                case "t":
                    text = title
                case "b":
                    text = body
                case _:
                    pass

            if copy_to_clipboard(text):
                console.print("[bold green]✓ Copied to clipboard.[/bold green]")
            else:
                err_console.print(
                    "[yellow]⚠ Could not access the system clipboard "
                    "(install 'pyperclip', or xclip/xsel on Linux).[/yellow]"
                )
            continue  # asking again

        elif choice == "r":
            title, body = generate_message()
            console.print(render_message(title, body))
            continue

        else:  # "n"
            console.print("[yellow]Aborted — nothing committed.[/yellow]")
            break
