# Commit Message Generator — System Prompt (v2)

Paste everything between the two `---` lines below into your local model's system prompt field, as-is.

> Maintainer note: this version assumes the CLI sends the model a `DIFF:` / `HINT:` wrapped message (see INPUT below) and that the CLI's Output Sanitizer extracts the two fenced blocks and joins them with a blank line for `git commit -m title -m body`. If you later add a `--conventional` flag for changelog-tool compatibility, swap the twelve capitalized type words below for their lowercase Conventional Commits equivalents (`feat, fix, refactor, style, perf, docs, style, test, chore, build, ci, revert`) — everything else stays identical.
