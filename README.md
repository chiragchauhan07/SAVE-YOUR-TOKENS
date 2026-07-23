# Save your Tokens

**An MCP Server for AI Repository Context Generation.**

Turn a software repository into a compact, structured briefing that an AI
coding agent can read in seconds instead of rediscovering by search.

> **Status: Phase 3 — Code Intelligence Engine.** The repository scanner,
> identification detectors, and Python code intelligence (entry points,
> routes, database models, authentication, configuration, import graph,
> important-file ranking) are implemented and tested. Context generation and
> the MCP server are not built yet. See the [Roadmap](#roadmap).

---

## The problem

Before an AI coding agent can change anything in an unfamiliar repository, it
has to work out what the repository *is*: entry points, frameworks, routes,
database layer, configuration, which files actually matter. It does that by
searching, reading, and searching again — and it repeats the same exploration
in the next session, and the one after that.

That rediscovery costs context window, time, and money, and it produces an
understanding that disappears when the session ends.

## The approach

Precompute the answers. `Save your Tokens` analyses a repository statically and
writes an AI-optimised context pack:

```
.ai-context/
├── OVERVIEW.md            What this project is
├── PROJECT_STRUCTURE.md   Directory map, annotated
├── ARCHITECTURE.md        Layers and how they connect
├── ENTRY_POINTS.md        Where execution begins
├── API_ROUTES.md          Discovered HTTP routes
├── DATABASE.md            Models, schemas, migrations
├── DEPENDENCIES.md        What it is built on
├── CONFIGURATION.md       Env vars and config surfaces
├── IMPORTANT_FILES.md     The files that actually matter
└── AI_CONTEXT.md          Condensed entry point for agents
```

An agent reads this first and starts from an accurate mental model.

This does not eliminate repository exploration — it removes the *repeated,
mechanical* part of it and replaces it with a structured project map.

## No LLM

**Version 1 uses no language model at all.** No Anthropic, OpenAI or Gemini
API. No API key, no per-run cost, no network call, no non-determinism.

Everything comes from static analysis: file walks, manifest parsing, framework
signatures, route extraction, config discovery. The same repository always
produces the same output.

An optional LLM enrichment layer may be added later. It will never be part of
the core.

## Features

**Available now (Phase 1 + 2 + 3)**

- Recursive repository scanning with directory pruning
- Deterministic, sorted, reproducible output
- Ignore rules covering Python, JS/TS, Java, Rust, Go and Dart ecosystems
- Binary, media and build-artefact filtering
- Repository statistics: file counts, size, extension breakdown, largest files
- Language detection, ordered by byte prevalence
- Framework detection (FastAPI, Django, Flask, Streamlit, Litestar, Sanic,
  React, Next.js, Vue, Nuxt, Express, NestJS, Angular, Svelte, Spring Boot,
  Laravel, Flutter) with confidence and evidence attached to every result
- Package manager detection (pip, Poetry, uv, Pipenv, npm, Yarn, pnpm, Bun,
  Maven, Gradle, Cargo, Go Modules)
- Build tool, CI/CD, containerization and configuration-surface detection
- Repository classification (Full Stack Web App, REST API, Frontend, Mobile
  App, Monorepo, CLI Tool, Python Library, AI/ML Project, Unknown)
- Python code intelligence via `ast` analysis (no source execution):
  entry points, import graph with circular-import detection, per-module
  metadata, FastAPI/Flask/Django routes, SQLAlchemy/Pydantic/Django ORM
  models, authentication mechanisms, configuration surfaces, module
  dependency relationships, evidence-ranked important files
- Typed `Project` model as the engine's public contract
- CLI with human and JSON output

**Planned**

- Context file generation (Phase 4)
- MCP server (Phase 5)

## Installation

Requires Python 3.11+. No runtime dependencies.

```bash
git clone https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS.git save-your-tokens
cd save-your-tokens
python -m pip install -e ".[dev]"
```

## Usage

```bash
python cli.py scan /path/to/repository
```

```
Repository  : my-api
Project Type: Full Stack AI Web Application
Path        : /home/dev/my-api

Languages:
  Python       72.0%  (140 files)
  TypeScript   25.0%  (60 files)
  CSS           3.0%  (12 files)

Frameworks:
  FastAPI
  React

Package Managers:
  Poetry
  npm

Build:
  Docker
  Vite

CI/CD:
  GitHub Actions

Containerization:
  Docker Compose

Environment:
  .env.example
  compose.yaml

Entry Points:
  app/main.py (fastapi_app)

Backend Routes: 27

Database Models: 12

Authentication:
  JWT

Main Configuration:
  Settings Module

Important Files:
  app/main.py
  app/database.py
  app/auth.py

Dependency Relationships: Available (41)

Files      : 284
Directories: 46
Total size : 1.8 MB

File types (top 15):
  .py                     183   64.4%
  .md                      31   10.9%
  .json                    24    8.5%

Largest files:
     94.1 KB  tests/fixtures/payload.json
     31.7 KB  app/services/billing.py
```

Machine-readable output:

```bash
python cli.py scan /path/to/repository --json
```

Options: `--ignore DIR` (repeatable), `--include-hidden`, `--follow-symlinks`.

Or use the engine directly:

```python
from analyzer import analyze_repository

project = analyze_repository("/path/to/repository")
print(project.repository_type)              # Detection(name='REST API', ...)
print([f.name for f in project.frameworks])  # ['FastAPI']
print(project.languages)                     # (LanguageStat(name='Python', ...), ...)
print(project.routes)                        # (Route(method='GET', path='/users', ...), ...)
print(project.entry_points)                  # (EntryPoint(kind='fastapi_app', ...), ...)

# Or run each phase separately:
from analyzer import scan_repository, identify_project, analyze_intelligence

project = scan_repository("/path/to/repository")
project = identify_project(project)      # languages, frameworks, ...
project = analyze_intelligence(project)  # entry points, routes, models, ...
```

## Architecture

```
Repository
    ↓
Analysis Engine      ← analyzer/   (deterministic, no MCP, no LLM)
                        scanner → detectors → intelligence
    ↓
Context Generator    ← Phase 4
    ↓
MCP Server           ← server.py   (thin adapter)
    ↓
Claude Code / Cursor / any MCP client
```

The engine is the product. MCP is one interface onto it — a CLI, a web app or
an HTTP API can be added without touching `analyzer/`.

Detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Roadmap

| Phase | Scope | Status |
|-------|-------------------------------------------|--------|
| 1 | Repository scanner, models, ignore rules  | Done |
| 2 | Project Identification Engine             | Done |
| 3 | Code Intelligence Engine                  | Done |
| 4 | Context file generation                   | Next |
| 5 | MCP server                                | Planned |
| 6 | Caching, incremental rescans, packaging   | Planned |

Detail in [docs/ROADMAP.md](docs/ROADMAP.md).

## Development philosophy

- **Deterministic over clever.** Reproducible beats impressive.
- **Separation of concerns.** Scanners scan, parsers parse, detectors detect,
  generators generate. Never mixed.
- **Standard library first.** Every dependency is a liability.
- **Extensible by data.** New ecosystems should mean new entries in
  `constants.py` or `detectors/signatures.py`, not new branches in a scanner
  or detector.
- **Never guess.** Every detection carries confidence and evidence; "unknown"
  is always a valid, honest result.
- **Static analysis, never execution.** Source code is parsed (`ast`), never
  imported, `exec`'d or `eval`'d — the tool must be safe to run unattended
  against any repository handed to it.
- **No premature optimisation.** Build the current phase well; leave notes for
  the next one.

## Testing

```bash
python -m pytest -q
```

## Documentation

- [CLAUDE.md](CLAUDE.md) — working agreement for AI sessions on this repo
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
- [docs/DECISIONS.md](docs/DECISIONS.md)
- [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md)
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

Version 1 performs static analysis only and uses no language model. Its output
is a structural map, not a semantic understanding of your code. It is designed
to make repository exploration cheaper, not to remove the need for it.
