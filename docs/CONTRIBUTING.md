# Contributing

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

Verify:

```bash
python -m pytest -q
python cli.py scan sample_repo
```

## Before you write code

1. Read [CLAUDE.md](../CLAUDE.md) — the non-negotiable rules.
2. Check [ROADMAP.md](ROADMAP.md) — is this in the current phase? If it belongs
   to a later phase, add it to the roadmap instead of building it now.
3. Skim [DECISIONS.md](DECISIONS.md) — the question may already be settled.

## The rules that get a change rejected

- **An LLM call in `analyzer/`.** Version 1 is deterministic. No exceptions.
- **`analyzer/` importing MCP, CLI or any interface layer.** Dependencies point
  one way.
- **Non-deterministic output.** If two scans can differ, it is a bug.
- **A new runtime dependency without a decision entry.** Standard library
  first.
- **Logic in `server.py` or `cli.py`.** Adapters adapt; the engine thinks.

## Workflow

1. Branch from `main`.
2. Make the change, with tests.
3. Run `python -m pytest -q` and `ruff check .`.
4. Update `CHANGELOG.md` under `[Unreleased]` if the change is user-visible.
5. Add to `docs/DECISIONS.md` if you made an architectural choice.
6. Open a pull request describing *why*, not just *what*.

Commit messages: imperative mood, one logical change per commit.

```
Add framework detection for FastAPI
Fix symlink handling in scanner walk
```

## Adding support for a new ecosystem

Most contributions are this, and most should be pure data.

**New ignore rules** — add entries to the relevant frozen set in
`analyzer/constants.py`. Nothing else should need to change. If it does, the
scanner is too clever; say so in the PR.

**New framework detector (Phase 2+)** — add a new detector module. Do not edit
existing detectors. A detector answers one question about one framework and
returns a confidence-scored result.

**New file-format parser (Phase 3+)** — one parser per format, knowing nothing
about the others. Use a real parser (`ast`, `tomllib`, `json`) over a regular
expression whenever one exists.

## Testing expectations

Every behavioural change carries a test. Use `tmp_path` to build fixture
repositories; never touch a real repository or the network.

```python
def test_prunes_ignored_directories(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "index.js").write_text("x")
    project = scan_repository(tmp_path)
    assert project.files == ()
```

Test the public API. Private helpers are covered through it.

## Reporting a bug

Include the repository shape that triggered it (a minimal directory tree),
the command run, what you expected, and what happened. A failing test is the
best bug report.
