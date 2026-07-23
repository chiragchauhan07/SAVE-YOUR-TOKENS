# CLAUDE.md

Instructions for Claude Code sessions working on this repository. Read this
before making changes.

## What this project is

**Save your Tokens** — an MCP server for AI repository context generation.

It analyses a software repository **deterministically** and emits concise,
AI-optimised context files into `.ai-context/`. An MCP-compatible coding agent
(Claude Code, Cursor, ...) reads those files to understand a codebase quickly,
instead of rediscovering its structure by searching from scratch every session.

It is a **repository intelligence engine**, not a coding agent and not a
replacement for one.

## Non-negotiable rules

1. **No LLM in the core.** No Anthropic, OpenAI, Gemini or any other model API
   anywhere in `analyzer/`. Every result is produced by static analysis. If a
   feature seems to need an LLM, it belongs in a future optional layer, not in
   the engine. This constraint is the product, not a limitation.
2. **The engine never depends on MCP.** `analyzer/` must not import `server.py`
   or any MCP library. The dependency arrow points one way:
   `analyzer/ <- server.py` and `analyzer/ <- cli.py`.
3. **Determinism.** Two scans of an unchanged repository must produce identical
   output. Sort before returning. Never let dict or filesystem ordering leak
   into results.
4. **No file content is read in Phase 1.** The scanner stats files; it does not
   open them.
5. **Stay in phase.** Do not implement future phases early. Leave a `TODO` or a
   note in `docs/ROADMAP.md` instead.

## Layout

```
analyzer/          The reusable engine. No MCP, no CLI, no I/O beyond reading.
  constants.py     Ignore rules as data. Add ecosystems here, not in scanner.
  models.py        Frozen dataclasses: FileInfo, RepositoryStats, Project.
  scanner.py       Phase 1: the repository walk.
  utils.py         Small shared helpers.
cli.py             Thin CLI over the engine. For inspection, not the product.
server.py          MCP entry point. Placeholder until Phase 5.
tests/             pytest, no fixtures beyond tmp_path.
sample_repo/       Small fake repo for eyeballing CLI output.
docs/              Architecture, roadmap, decisions, standards.
```

## Current state

**Phase 1 is complete.** The repository scanner works, is tested, and is the
only implemented feature. `Project` is the contract every later phase consumes.

Phase 2 (language and framework detection) is next. See `docs/ROADMAP.md`.

## Conventions

- Python 3.11+, full type hints, `from __future__ import annotations`.
- `pathlib` over `os.path`. The one exception is `os.walk` in the scanner,
  which is used because it can prune directories mid-walk and `Path.rglob`
  cannot — see `docs/DECISIONS.md`.
- Frozen dataclasses over dictionaries for anything structured.
- Standard library first. A new runtime dependency needs a decision entry.
- Docstrings explain *why*; the code already says *what*.

Full detail in `docs/CODING_STANDARDS.md`.

## Working commands

```bash
python cli.py scan .              # human summary
python cli.py scan . --json       # machine-readable
python -m pytest -q               # test suite
ruff check .                      # lint
```

## Before you finish a change

- Tests pass.
- New behaviour has a test.
- An architectural choice made along the way is recorded in
  `docs/DECISIONS.md`.
- User-visible changes are in `CHANGELOG.md`.
