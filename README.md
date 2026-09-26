# Kothon

Kothon is an evidence-first Bengali subtitle and closed-caption pipeline. It
is designed for Bengali speech, Bengali/English/Hindi code-mixing, explicit
subtitle engineering rules, self-verification, accessibility tagging, and
reviewable compliance flags.

The project keeps model inference behind provider interfaces. The default
development configuration uses fixtures, so deterministic tests do not need
local model weights or a remote API key. Groq integrations are optional and
configured through environment variables.

## Development

```powershell
uv sync --extra dev --extra audio
uv run pytest
uv run ruff check .
uv run mypy src
```

The CLI and service layers are being built on top of the same typed pipeline
contracts. See `AGENTS.md` for the behavioral contract of every pipeline
stage and `PRD.md` for product scope.

