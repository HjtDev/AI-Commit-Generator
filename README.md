# AI Git Commit Generator

A CLI tool that reads your `git diff`, sends it to a local or cloud LLM
(LM Studio, Ollama, or any OpenAI-compatible endpoint), and generates a
structured semantic commit message — title + bulleted description — which you
can commit, edit, copy, or discard right from the terminal.

---

## ✨ Features

- **Semantic commit generation** — `<Type>(<scope>): <summary>` title plus a
  dashed-bullet description, driven by a fixed system prompt contract.
- **Interactive workflow** — preview the message, then **[Y]** commit,
  **[E]** edit in `$EDITOR`, **[C]** copy to clipboard, or **[N]** abort.
- **Multi-provider** — works with LM Studio, Ollama, or any
  OpenAI-compatible API (including hosted ones, with an API key).
- **Persistent config** — provider/model/behavior settings saved to disk and
  reused on every run.
- **`--hint` support** — pass extra developer context alongside the diff.
- **Streaming or blocking generation** — watch tokens arrive live, or wait
  for the full response.
- **Robust guards** — empty-diff detection, non-repo detection, oversized-diff
  truncation (lockfiles deprioritized first), and clear provider-vs-model
  error messages.

---

## 📦 Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- Git
- A running LLM provider — **LM Studio**, **Ollama**, or an
  OpenAI-compatible API — loaded with an instruction-following model
  **above 3B parameters**. `qwen2.5-coder-7b-instruct` is the recommended
  model — it reliably holds onto the structured two-block format. Anything
  under ~7B may still struggle to follow the contract consistently, and
  sub-3B models tend to lose the format entirely.

---

## 🚀 Installation

```bash
git clone <your-repo-url>
cd AI-Commit-Generator
uv sync
```

---

## ⚡ Quick Start

1. **Start your provider.**

2. **Point the tool at it.** LM Studio and Ollama both expose an
   OpenAI-compatible route under `/v1` — don't forget that suffix, it's the
   most common setup mistake (LM Studio's *native* API lives at a different
   path, `/api/v1/...`, with a different response shape entirely):

   ```bash
   uv run main.py config set --endpoint http://127.0.0.1:1234/v1 --model qwen2.5-coder-7b-instruct
   ```
   
    To See more run:
    ```
    uv run main.py config --help
    uv run main.py config set --help
    ```

3. **Stage some changes and generate:**

   ```bash
   git add .
   uv run main.py
   ```

---

## 🖥 CLI Usage

### Generate a commit message

Running the tool with no subcommand generates from your **staged** diff and
drops into the interactive prompt:

```bash
uv run main.py [OPTIONS]
```

| Flag | Short | Description |
|---|---|---|
| `--hint TEXT` | `-H` | Extra context about the change to guide the model (e.g. `--hint "added dark mode toggle"`) |
| `--yes` | `-y` | Skip the interactive prompt and commit immediately |
| `--unstaged` | `-u` | Generate from the unstaged diff instead of the staged one |
| `--no-stream` | | Wait for the full response instead of streaming tokens live |
| `--dry-run` | | Generate and preview the message, but never commit |
| `--path PATH` | `-p` | Path to the git repository (defaults to the current directory) |
| `--max-diff-chars INT` | | Truncate diffs larger than this many characters (default `4000`) |
| `--model TEXT` | `-m` | Override the configured model for this run only |
| `--endpoint TEXT` | | Override the configured provider endpoint for this run only |
| `--version` | | Show the version and exit |

**Examples**

```bash
# Standard interactive run
uv run main.py

# Add developer context, commit without asking
uv run main.py --hint "refactored auth middleware" --yes

# Preview only, no commit — for checking diff truncation or a new model
uv run main.py --dry-run

# One-off run against a different model without touching saved config
uv run main.py --model qwen2.5-coder-7b-instruct

# Generate from unstaged changes in another repo
uv run main.py --unstaged --path ../other-project
```

### Interactive workflow

After generation, you'll see the proposed message and a prompt:

```
[Y]es commit  [E]dit  [C]opy  [N]o abort
```

- **Y** — runs `git commit -m "<title>" -m "<body>"` immediately.
- **E** — opens the message in `$EDITOR` (falls back to `nano`/`notepad`);
  the edited first line becomes the title, everything after it becomes the
  body, then you're shown the result and asked again.
- **C** — copies `title\n\nbody` to the system clipboard (via `pyperclip` if
  installed, otherwise `pbcopy`/`xclip`/`xsel`/`clip`) and returns you to the
  prompt — copying doesn't end the session, so you can still commit or edit
  afterward.
- **N** — aborts. Nothing is committed.

### Config management

All config lives under the `config` subcommand:

```bash
uv run main.py config show                     # print the current config
uv run main.py config path                      # print the config file location
uv run main.py config set [OPTIONS]              # update one or more values
uv run main.py config reset [--yes]              # reset to defaults
```

`config set` options:

| Flag | Description |
|---|---|
| `--endpoint TEXT` | Provider base URL, e.g. `http://localhost:1234/v1` |
| `--api-key TEXT` | API key (leave unset for most local servers) |
| `--model TEXT` | Model name/id to request from the provider |
| `--conventional` / `--no-conventional` | Lowercase Conventional Commit types vs. capitalized custom types |
| `--auto-commit-on-success` / `--no-auto-commit-on-success` | Skip the interactive prompt and commit automatically whenever generation succeeds |
| `--timeout INT` | Request timeout in seconds |
| `--retries INT` | Number of retries on request failure |

```bash
uv run main.py config set --endpoint http://127.0.0.1:1234/v1 --model qwen2.5-coder-7b-instruct --timeout 60
```

### Web UI

```bash
uv run main.py serve
```

Not implemented yet — `ui/backend` and `ui/frontend` are placeholders for a
future FastAPI + static Next.js build that will reuse the same `core`
package. Running `serve` today prints a note and exits.

---

## ⚙️ Configuration file

Config is a JSON file, loaded via `pydantic-settings` and saved automatically
on first run:

- Linux/macOS/Windows: `core/config.json` (next to the package), or override the
  path via the `AI_COMMIT_*` environment variables / an `.env` file.

```json
{
  "endpoint": "http://127.0.0.1:1234/v1",
  "api_key": null,
  "model": "qwen2.5-coder-7b-instruct",
  "conventional": true,
  "auto_commit_on_success": false,
  "timeout": 30,
  "retries": 3
}
```

---

## 🔗 System Prompt

The fixed system prompt lives at `core/docs/System-Prompt.md` and is the
contract between the core generation logic and the model — it applies
identically no matter which provider is configured.

- **Type** is always one of: `Feature, Fix, Refactor, Polish, Perf, Docs,
  Style, Test, Chore, Build, CI, Revert`. Set `conventional: true` in the
  config to lowercase these into standard Conventional Commit types
  (`feat`, `fix`, ...) at request time — no prompt edits required.
- **Output shape** is exactly two fenced code blocks: the title line, then
  the bulleted description. The core's output parser (`core/llm.py`) is
  built around this exact two-block contract, splitting on all fences
  present rather than assuming a single wrapping block — so it degrades
  gracefully even if a smaller model only manages one block, or none.
- **Input shape** sent to the model is always `DIFF:` (the possibly
  truncated diff) followed by `HINT:` (your `--hint` value, or the literal
  string `(none provided)`).

---

## 🩹 Troubleshooting

- **`Could not reach the model provider`** — is the server actually running?
  Does the endpoint include the `/v1` suffix?
- **`The model responded, but returned an unusable message`** — the model
  ignored the fenced-block format. Try `--no-stream`, a different (larger)
  model, or double-check `core/docs/System-Prompt.md` is still in place.
- **Garbled or off-topic output** (e.g. the model rambling in code that has
  nothing to do with your diff) — usually means the loaded model is too
  small to reliably follow the structured prompt. Use `qwen2.5-coder-7b-instruct`
  or similar; models under ~7B may not be suitable enough to hold the
  two-block format consistently, and anything at or below 3B tends to lose
  it entirely.
- **`No staged changes detected`** — run `git add <files>` first, or pass
  `--unstaged` to generate from unstaged changes instead.

---

## 📁 Project Structure

```
AI-Commit-Generator/
├── core/                       # shared package: git ops, config, LLM calls
│   ├── config.json             # persisted user config (generated on first run)
│   ├── docs/
│   │   ├── README.md
│   │   └── System-Prompt.md    # the fixed model contract
│   ├── git.py                  # Git — diff/commit via subprocess
│   ├── llm.py                  # LLMService — provider calls + output parsing
│   ├── settings.py             # Config (pydantic-settings) — load/save
│   ├── __init__.py
│   └── tests/
│       ├── test_config.py
│       ├── test_git.py
│       └── test_llm.py
├── ui/
│   ├── backend/                # future FastAPI app (not yet built)
│   └── frontend/               # future Next.js static export (not yet built)
├── main.py                     # Typer + Rich CLI entry point
├── pyproject.toml
├── uv.lock
├── LICENSE.md
└── README.md
```

---

## 🗺️ Status

- ✅ Core package: git diff/commit, config persistence, multi-provider LLM
  calls, streaming + non-streaming generation, output parsing.
- ✅ CLI: interactive Y/E/C/N flow, `--hint`, `--yes`, `--unstaged`,
  `--dry-run`, `--no-stream`, diff truncation, config subcommands,
  per-run `--model`/`--endpoint` overrides.
- ⏳ Web UI (`serve` command, FastAPI + static Next.js): not started.
- ⏳ `--conventional` is already wired into config/prompt handling; no
  further work needed there.
