# AI Git Commit Generator — Specification & Requirements (v3, Finalized)

## 🎯 Overview
A fast, configurable tool that leverages local LLMs (via LM Studio, Ollama, etc.) or cloud APIs to analyze staged `git diff` changes and automatically generate structured, semantic commit messages and multi-line descriptions — usable either as a terminal CLI or through a locally-served browser UI.

---

## 🧰 Tech Stack

- **Core:** Python. Houses the provider abstraction (LM Studio/Ollama/OpenAI-compatible), the diff reader/truncator, the output sanitizer, and config load/save — used identically by both the CLI and the Web UI's API layer, so the generation logic exists in exactly one place.
    - CLI parsing/subcommands: `typer` (or `click`)
    - Terminal styling + interactive Y/E/C/N prompt: `rich` + `questionary`
    - Git operations: `subprocess` calls to the real `git` binary (avoids reimplementing diff/commit semantics), or `GitPython` if a Python-native API is preferred
    - Calling the model provider: `httpx` (async-friendly, works well with FastAPI)
    - Config validation: `pydantic` models, persisted as JSON
- **Backend (Web UI mode):** FastAPI + Uvicorn. Exposes a small REST API (`/api/diff`, `/api/generate`, `/api/commit`, `/api/config`) and mounts the pre-built Next.js static export via `StaticFiles`.
- **Frontend (Web UI mode):** React / Next.js, built with `output: 'export'` for a fully static build. No Node.js runtime is needed in production — FastAPI just serves the resulting HTML/JS/CSS. Node is only a build-time dependency for whoever packages a release.
- **Distribution:** packaged as a pip/pipx-installable Python package (`pipx install ai-git-commit-generator`) with a `git-auto-commit` console-script entry point. The Next.js static export is built once and bundled into the package's `static/` folder before publishing — end users never need Node.js installed to *use* the tool, only the maintainer needs it to *build* a release.

---

## 🛠 Feature Requirements

### 1. Commit Message & Description Generation
* **Semantic Format:** `<type>(<scope>): <summary>` title followed by a bulleted, line-by-line detailed description. See **System Prompt Integration** below for the exact contract.
* **Context Preservation:** Parses both staged code modifications and optional user guidance (`--hint`).
* Shared by both modes: the Web UI calls the same core generation function the CLI calls, just through a FastAPI route instead of a direct function call.

### 2. CLI Mode — Execution & Commit Options
* **Interactive Mode (default):** Preview the generated commit title and description, with prompts to:
    * **[Y] Commit:** Execute `git commit -m "<title>" -m "<body>"` immediately.
    * **[E] Edit:** Open the generated message in `$EDITOR` before committing (`git commit -e -m ...`).
    * **[C] Copy:** Copy the text to the system clipboard without committing.
    * **[N] Abort:** Cancel the operation.
* **Direct Commit Flag:** `--yes` / `-y` commits instantly without interactive confirmation.

### 3. API & Model Configuration (One-Time Setup)
* **Persistent Configuration:** Stored as JSON (see **Config Schema** below) at `~/.config/git-auto-commit/config.json` (macOS/Linux) or `%APPDATA%\git-auto-commit\config.json` (Windows). Shared by CLI and Web UI mode — editing it in one place affects both.
* **Multi-Provider Support:**
    * LM Studio (OpenAI-compatible local server at `http://localhost:1234/v1`)
    * Ollama local server (`http://localhost:11434/v1`)
    * OpenAI API / custom OpenAI-compatible endpoints
* **Config CLI Commands:**
    * `git-auto-commit config --provider lm-studio --url http://localhost:1234/v1 --model qwen2.5-coder`
    * Saved defaults load automatically on subsequent runs without re-specifying arguments.

### 4. User Prompt Hints / Context Injection
* **Hint Flag/Field:** `--hint "added dark mode toggle"` in CLI mode, or a text field in Web UI mode — injects extra developer intent alongside the raw diff.
* **Combined Prompting:** The model receives both `git diff --staged` and the hint, wrapped in the fixed `DIFF:` / `HINT:` contract defined in the system prompt file — this exact shape is what makes hint-vs-diff precedence work reliably on a small model.

### 5. Robust Error Handling
* **Empty Diff Detection:** Guard against running when `git diff --staged` is empty, prompting the user to run `git add` (CLI) or showing the same message in the Web UI. The model is never invoked on a genuinely empty diff — this is caught before making the call. The system prompt's own "no changes detected" fallback is a defensive second layer, not the primary guard.
* **API Unreachable / Timeout:** Handle connection-refused errors gracefully with actionable troubleshooting tips (e.g. "Is LM Studio's server running?"), surfaced in both the terminal and as a Web UI error toast/banner.
* **Large Diff Truncation:** Slice diffs over `maxDiffChars` (default 4000) to avoid context overflow or slow local inference, prioritizing modified source over auto-generated lockfiles. Insert a visible truncation marker so the model knows not to assume completeness (see system prompt's INPUT section).
* **Non-Git Directory Check:** Verify execution happens inside a valid git repository before running any git commands, in both modes.

### 6. Output Sanitization & Formatting
* **Fence Extraction:** Parse the model's two fenced code blocks and join them with a blank line for `git commit -m title -m body` (this is why the system prompt insists on that exact two-block shape — the sanitizer is built around it, not a generic strip-and-hope).
* **Preamble Removal:** Strip any conversational artifacts ("Here is your commit message:", trailing remarks) as a fallback, in case the model doesn't fully comply.
* **Standardized Structure:** Guarantee a clean single title line, blank-line separator, and clean bullets — whether the result is handed to `git commit` directly (CLI) or returned as JSON to the frontend (Web UI).

### 7. Web UI Mode
* **Launch:** `git-auto-commit serve` starts the FastAPI server and serves the static Next.js build at `http://127.0.0.1:<port>` (default port configurable, see Config Schema).
* **Core flow (mirrors CLI mode):** view the current staged diff, generate a commit message, edit the title/body in the browser before committing, and commit with one click — same underlying core functions as the CLI, just reached over HTTP.
* **API surface:**
  | Route | Purpose |
  |---|---|
  | `GET /api/diff` | Return the current staged diff (and whether it's truncated) |
  | `POST /api/generate` | Send diff + optional hint to the configured provider, return the parsed title/body |
  | `POST /api/commit` | Run `git commit` with the (possibly edited) title/body |
  | `GET/POST /api/config` | Read or update the persisted config |

---

## 🔗 System Prompt Integration

The fixed system prompt lives in `commit-message-system-prompt.md` (v2) — treat it as the contract between the core generation logic and the model, not something to improvise around per call. It's provider- and frontend-agnostic, so it applies identically whether the request originates from the CLI or from `/api/generate`. Two decisions are locked in there:

1. **Type casing:** capitalized custom types (`Feature`, `Fix`, `Polish`, etc.) are kept for v1, for personal readability. A future `--conventional` flag/config toggle can swap in lowercase Conventional Commits types (`feat`, `fix`, ...) — that's a one-line edit to the type list in the prompt file plus flag plumbing in the config, no other code changes needed.
2. **Input contract:** the core must assemble the message sent to the model as `DIFF:` (the possibly-truncated diff) followed by `HINT:` (the hint value, or the literal string `(none provided)`). The model relies on this exact shape to weigh hint-vs-diff correctly.

---

## ⚙️ Config Schema

```json
{
  "provider": "lm-studio",
  "url": "http://localhost:1234/v1",
  "model": "qwen2.5-coder",
  "conventional": false,
  "maxDiffChars": 4000,
  "web": {
    "host": "127.0.0.1",
    "port": 4321
  }
}
```

---

## 📖 CLI Command Reference

| Command | Description |
|---|---|
| `git-auto-commit` | Generate + interactive preview (default, CLI mode) |
| `git-auto-commit -y` / `--yes` | Generate + commit immediately, no prompt |
| `git-auto-commit --hint "..."` | Add developer context to the prompt |
| `git-auto-commit config --provider <p> --url <u> --model <m>` | Persist provider settings |
| `git-auto-commit config --conventional` | Toggle lowercase Conventional Commit types |
| `git-auto-commit serve` | Launch the FastAPI server + Web UI |
| `git-auto-commit serve --port 8080 --open` | Override the port and auto-open the browser |

---

## 📁 Project Structure

```
ai-git-commit-generator/
├── core/                    # shared Python package: provider abstraction, sanitizer,
│   │                        # diff truncation, config load/save (used by both modes)
│   ├── providers.py
│   ├── sanitizer.py
│   ├── diff.py
│   └── config.py
├── cli/                     # typer app — the terminal experience
│   └── main.py
├── api/                     # FastAPI app — routes for Web UI mode
│   ├── app.py
│   └── routes/
├── web/                     # Next.js frontend source (built separately)
│   ├── app/
│   └── next.config.js       # output: 'export'
├── static/                  # built Next.js export gets copied here before packaging
├── commit-message-system-prompt.md
└── pyproject.toml
```

---

## 🚀 Architecture Diagram / Flow

```
                [git diff --staged] + [hint (optional)]
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
        [CLI (typer)]                 [Web UI (Next.js, static)]
              │                               │
              │                       [FastAPI routes /api/*]
              └───────────────┬───────────────┘
                              ▼
                     [Shared Core Package]
                  (config, provider call, sanitizer)
                              │
                              ▼
              [LM Studio / Ollama / API Endpoint]
                              │
                              ▼
                      [Output Sanitizer]
              (extracts two fenced blocks, strips stray preamble)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   [CLI interactive prompt]           [Browser preview + edit]
   Y: commit / E: edit /              one-click commit via
   C: copy / N: abort                 POST /api/commit
```

---

## 🗺️ Roadmap

- **v0.1** — Core package + CLI: staged diff → single hardcoded provider (LM Studio) → sanitizer → interactive commit prompt.
- **v0.2** — Config persistence (`config.json`) + multi-provider support (Ollama, OpenAI-compatible) + `--hint` flag.
- **v0.3** — Error handling hardening: empty diff guard, unreachable-API messaging, large-diff truncation with marker.
- **v0.4** — FastAPI + statically-exported Next.js Web UI wrapping the same core package (`serve` command, `/api/*` routes).
- **v1.0** — `--conventional` flag, polish pass, publish to PyPI (with the frontend pre-built and bundled in).
