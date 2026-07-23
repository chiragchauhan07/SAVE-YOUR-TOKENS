# Blueprint

**Deterministic repository analysis for AI coding agents, over the Model
Context Protocol.**

> Formerly "Save your Tokens." Same engine, same guarantees, new name —
> see [Rebrand](#rebrand-from-save-your-tokens) below if you're upgrading.

Turn a software repository into a compact, structured briefing that an AI
coding agent can read in seconds instead of rediscovering by search.

> **Status: Phase 6 complete, first stable release under the Blueprint
> name.** The repository scanner, identification detectors, Python code
> intelligence, the `.blueprint/` Knowledge Base generator, the MCP
> server, and an incremental re-analysis engine are all implemented and
> tested. See the [Roadmap](#roadmap) and
> [docs/MCP_SERVER.md](docs/MCP_SERVER.md) for MCP installation and
> client configuration.

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

Precompute the answers. `Blueprint` analyses a repository statically and
writes an AI-native Knowledge Base:

```
.blueprint/
├── AI_CONTEXT.md          Start here — reading order, entry points, critical files
├── INDEX.md               Table of contents for the whole Knowledge Base
├── OVERVIEW.md            Repository type, languages, frameworks, tech stack
├── PROJECT_STRUCTURE.md   File/directory statistics, largest files
├── ARCHITECTURE.md        Entry points, most important files, dependency summary
├── MODULES.md             Classes, functions, constants, exports — per module
├── DEPENDENCIES.md        Full import graph, circular imports, external packages
├── API_ROUTES.md          Discovered HTTP routes
├── DATABASE.md            Detected ORM/schema models
├── AUTHENTICATION.md      Detected authentication mechanisms
├── CONFIGURATION.md       Settings modules, config classes, env/dotenv usage
└── IMPORTANT_FILES.md     The complete evidence-ranked file list
```

Every file ends with a **Related Context** section linking to related files —
the Knowledge Base behaves like an interconnected graph, not isolated
documents. An agent reads `AI_CONTEXT.md` first and starts from an accurate
mental model before opening a single source file.

This does not eliminate repository exploration — it removes the *repeated,
mechanical* part of it and replaces it with a structured, navigable map.
Nothing in the Knowledge Base ever copies source code: it represents
*extracted* facts (a route's method and path, a model's fields, a module's
class names), never function bodies or file contents.

## No LLM

**Version 1 uses no language model at all.** No Anthropic, OpenAI or Gemini
API. No API key, no per-run cost, no network call, no non-determinism.

Everything comes from static analysis: file walks, manifest parsing, framework
signatures, route extraction, config discovery. The same repository always
produces the same output.

An optional LLM enrichment layer may be added later. It will never be part of
the core.

## Features

**Available now (Phase 1 through 6)**

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
- AI-native Knowledge Base generation: twelve deterministic, cross-referenced
  Markdown files in `.blueprint/`, every file always present with graceful
  "none detected" content, never a copy of source code
- An MCP server (six tools: `analyze_repository`, `repository_summary`,
  `generate_knowledge_base`, `health_check`, `repository_changes`,
  `clear_cache`) exposing the same engine over the Model Context Protocol —
  byte-identical output to the CLI, safe structured error handling, stdio
  transport
- Incremental re-analysis: a persistent cache detects new/modified/
  deleted/renamed files, reuses prior analysis wherever it's provably safe
  to, and regenerates only the Knowledge Base documents that actually
  changed — always falls back to a full analysis if the cache is missing,
  corrupted, or from a different tool version, and always produces
  byte-identical output to a full regeneration
- Typed `Project` model as the engine's public contract
- CLI with human and JSON output, plus `generate` for a full Knowledge
  Base build and `update`/`cache-info`/`cache-clear` for incremental use

## Installation

Requires Python 3.11+. The analysis engine and Knowledge Base generator
have no runtime dependencies; the MCP server needs the official `mcp` SDK
(the project's only dependency, and only for that layer).

```bash
git clone https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS.git blueprint
cd blueprint
python -m pip install -e ".[dev]"      # CLI + generator + MCP server + dev tools
```

CLI and generator only, no MCP:

```bash
python -m pip install -e .
```

MCP server only (as a published package, once released):

```bash
python -m pip install "blueprint[mcp]"
```

This installs the `blueprint` and `blueprint-mcp` console scripts.
`save-your-tokens` and `save-your-tokens-mcp` are still installed as
deprecated aliases during the transition — see
[Rebrand](#rebrand-from-save-your-tokens) below.

## Usage

```bash
blueprint scan /path/to/repository
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
blueprint scan /path/to/repository --json
```

Options: `--ignore DIR` (repeatable), `--include-hidden`, `--follow-symlinks`.

Generate the Knowledge Base:

```bash
blueprint generate /path/to/repository
```

```
Generated 12 files in /path/to/repository/.blueprint
  AI_CONTEXT.md
  API_ROUTES.md
  ARCHITECTURE.md
  AUTHENTICATION.md
  CONFIGURATION.md
  DATABASE.md
  DEPENDENCIES.md
  IMPORTANT_FILES.md
  INDEX.md
  MODULES.md
  OVERVIEW.md
  PROJECT_STRUCTURE.md
```

`--output DIR` writes elsewhere instead of `<path>/.blueprint`.

Incremental regeneration — reuses the cache from a prior `update` (or
`generate`), re-analysing and rewriting only what actually changed:

```bash
blueprint update /path/to/repository
```

```
Cache: valid
  new: 0
  modified: 1
  deleted: 0
  renamed: 0
  unchanged: 74

Files analyzed: 1
Files reused  : 74

Knowledge regenerated:
  API_ROUTES.md
  AI_CONTEXT.md

Knowledge unchanged: 10 document(s)

Duration: 0.39s
```

`--force` ignores the cache and re-analyses fully (still writes
byte-identical output to a plain incremental run against the same state).
`cache-info` and `cache-clear` inspect and delete the cache:

```bash
blueprint cache-info /path/to/repository
blueprint cache-clear /path/to/repository
```

Or use the engine and generator directly:

```python
from pathlib import Path

from analyzer import analyze_repository
from generator import generate_knowledge_base, write_knowledge_base

project = analyze_repository("/path/to/repository")
print(project.repository_type)              # Detection(name='REST API', ...)
print([f.name for f in project.frameworks])  # ['FastAPI']
print(project.languages)                     # (LanguageStat(name='Python', ...), ...)
print(project.routes)                        # (Route(method='GET', path='/users', ...), ...)
print(project.entry_points)                  # (EntryPoint(kind='fastapi_app', ...), ...)

documents = generate_knowledge_base(project)  # {"OVERVIEW.md": "# Overview\n...", ...}
write_knowledge_base(project, Path("/path/to/repository/.blueprint"))

# Or run each phase separately:
from analyzer import scan_repository, identify_project, analyze_intelligence

project = scan_repository("/path/to/repository")
project = identify_project(project)      # languages, frameworks, ...
project = analyze_intelligence(project)  # entry points, routes, models, ...
```

## MCP server

Six tools over the Model Context Protocol — same engine, same results as
the CLI, including incremental updates:

```bash
python server.py                # run over stdio
blueprint-mcp                    # equivalent, once installed
```

Claude Code configuration (`.mcp.json`):

```json
{
  "mcpServers": {
    "blueprint": {
      "command": "blueprint-mcp"
    }
  }
}
```

Full tool reference, example requests/responses, other client
configurations, error types and limitations:
[docs/MCP_SERVER.md](docs/MCP_SERVER.md).

## Architecture

```
Repository
    ↓
Analysis Engine          ← analyzer/     (deterministic, no MCP, no LLM)
                            scanner → detectors → intelligence
                            analyzer/caching/ — incremental re-analysis
    ↓
Knowledge Base Generator ← generator/    (Project → .blueprint/, the primary output)
    ↓
Incremental Orchestrator ← incremental/  (update/preview/inspect/clear the cache)
    ↓
MCP Integration Layer    ← mcp_server/   (thin adapter, 6 tools)
    ↓
server.py, cli.py        (entry points)
    ↓
Claude Code / Cursor / any MCP client
```

The engine discovers, the generator organizes, interfaces expose.
`generator/` consumes only `analyzer.models.Project`; `mcp_server/` consumes
only the public APIs of `analyzer/` and `generator/`. Neither re-scans,
re-parses, or touches the analyzed repository's source beyond what the
engine already extracted. A web app or an HTTP API could be added the same
way, without touching `analyzer/`, `generator/`, or `mcp_server/`.

Detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Roadmap

| Phase | Scope | Status |
|-------|-------------------------------------------|--------|
| 1 | Repository scanner, models, ignore rules  | Done |
| 2 | Project Identification Engine             | Done |
| 3 | Code Intelligence Engine                  | Done |
| 4 | AI Knowledge Base Generator                | Done |
| 5 | MCP Integration Layer                     | Done |
| 6 | Incremental Intelligence Engine            | Done |
| — | Rebrand: Save your Tokens → Blueprint      | Done |

Detail in [docs/ROADMAP.md](docs/ROADMAP.md).

## Rebrand from "Save your Tokens"

The project was originally released as **Save your Tokens**. As of v1.0.0
it's **Blueprint** — same engine, same deterministic guarantees, same
production quality; only the name, the default output directory and the
console script names changed.

- **Knowledge Base directory:** `.ai-context/` → `.blueprint/`. If a
  repository still has a `.ai-context/` directory at the default location,
  the next `generate` or `update` call (CLI or MCP) renames it to
  `.blueprint/` automatically, in place — the existing Knowledge Base and
  incremental cache are preserved, not regenerated from scratch. A custom
  `--output`/`output_dir` is never touched by this migration.
- **Incremental cache:** migrates along with the directory above. Because
  this release also bumps the tool version, a migrated cache is
  automatically recognised as being from an older version and triggers one
  full re-analysis (not a partial/incorrect one) the first time it's used
  after upgrading — then a fresh, valid cache is written. You never end up
  with stale or corrupted state.
- **CLI:** `save-your-tokens` / `save-your-tokens-mcp` still work — both
  are installed as deprecated aliases pointing at the exact same code —
  but print a one-time deprecation notice to stderr pointing at
  `blueprint` / `blueprint-mcp`.
- **Environment variable:** `SAVE_YOUR_TOKENS_LOG_LEVEL` still works as a
  deprecated fallback for `BLUEPRINT_LOG_LEVEL` (a warning is logged if
  only the old name is set).
- **Python package name:** `save-your-tokens` → `blueprint` in
  `pyproject.toml`. Nothing has been published to PyPI under either name
  yet, so this is a plain rename with no migration hazard.

See `docs/DECISIONS.md` (D-053) for the full rationale.

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
- **Discover once, organize separately.** The analysis engine discovers
  facts; the Knowledge Base generator only organizes and presents them —
  never re-scans, re-parses, or copies source code into generated output.
- **No premature optimisation.** Build the current phase well; leave notes for
  the next one.

## Testing

```bash
python -m pytest -q
```

## Documentation

- [CLAUDE.md](CLAUDE.md) — working agreement for AI sessions on this repo
- [docs/MCP_SERVER.md](docs/MCP_SERVER.md) — MCP installation, client
  configuration, tool reference
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
