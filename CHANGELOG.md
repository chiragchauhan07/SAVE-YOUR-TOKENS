# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No active development. Phase 5 completed the first production-ready
release; see [docs/ROADMAP.md](docs/ROADMAP.md) for possible future work.

## [0.5.0] — 2026-07-23

Phase 5: the MCP Integration Layer — this project's first production-ready
release. Exposes the analysis engine and Knowledge Base generator through
the Model Context Protocol, as a thin adapter with no analysis logic of its
own.

### Added

- `mcp_server/` — a new top-level package using the official MCP Python
  SDK (`mcp.server.fastmcp.FastMCP`), stdio transport. `handlers.py` holds
  pure business logic with zero MCP SDK imports (testable directly);
  `tools.py` is the only module that imports the SDK.
- Four MCP tools:
  - `analyze_repository` — analyse a repository, optionally also generate
    (and optionally write) its Knowledge Base, from a single analysis pass.
  - `repository_summary` — a fast, structured overview (type, languages,
    frameworks, entry points, routes, database models, important files,
    authentication, configuration) without generating the Knowledge Base.
  - `generate_knowledge_base` — generate and write the `.ai-context/`
    Knowledge Base; returns file names and byte counts, never document
    content.
  - `health_check` — package version, MCP SDK version, and environment
    information, for diagnosing an installation.
- Professional error handling: every tool catches its own exceptions and
  returns `{"success": false, "error": {"type": ..., "message": ...}}`
  rather than propagating a raw exception — confirmed by direct testing
  that the SDK's own exception wrapping echoes the original exception
  message verbatim, which is not safe to trust by default. Six error
  types: `repository_not_found`, `invalid_repository`,
  `permission_denied`, `analysis_failed`, `generation_failed`,
  `internal_error`.
- Structured logging to stderr only (`WARNING` by default, configurable via
  `SAVE_YOUR_TOKENS_LOG_LEVEL`) — stdout is reserved for the MCP protocol
  stream on stdio transport.
- `analyzer/serialization.py` — the JSON-conversion helpers that used to be
  private to `cli.py`, extracted so the CLI and MCP server share one
  implementation instead of two.
- Root `server.py` implemented as a thin shim over `mcp_server/`, the same
  role `cli.py` already has over `analyzer`/`generator`.
- `save-your-tokens-mcp` console script; `mcp` and `dev` optional-dependency
  groups now include the official `mcp` SDK (`mypy` was also added to
  `dev`, closing a gap where it had been used for verification since
  Phase 1 without ever being declared).
- `docs/MCP_SERVER.md` — installation, an example Claude Code
  configuration, the full tool reference with example requests/responses,
  supported clients, error types, and known limitations.
- 35 new tests: handler-level unit tests for every tool and error path, a
  single-analysis-per-call regression guard, FastMCP tool-registration and
  in-process invocation tests, a byte-for-byte CLI/MCP output parity test,
  and one real stdio-transport integration test that spawns `server.py` as
  a subprocess and speaks actual MCP protocol to it via the official
  client SDK.

### Notes

- Still no LLM anywhere in `analyzer/` or `generator/`. The MCP SDK is this
  project's first runtime dependency, and it is scoped to `mcp_server/`
  only — installing `save-your-tokens` without the `mcp` extra still gets a
  dependency-free analysis engine and generator.
- Verified end-to-end: a real (non-editable) wheel build included every new
  subpackage on the first attempt; installed into a clean virtual
  environment; both console scripts (`save-your-tokens`,
  `save-your-tokens-mcp`) exercised from that install; the installed MCP
  server driven over a real stdio subprocess by the official client SDK.
- Dogfooded against this repository: the Knowledge Base generated via the
  MCP server and the one generated via `python cli.py generate .` are
  byte-identical, file for file.

## [0.4.0] — 2026-07-23

Phase 4: the AI Knowledge Base Generator — this project's primary output.
Turns a fully analysed `Project` into a deterministic, cross-referenced
`.ai-context/` Markdown Knowledge Base, without re-scanning, re-parsing, or
copying any source code.

### Added

- `generator/` — a new top-level package (sibling to `analyzer/`, not
  nested under it — see D-028), consuming only `analyzer.models.Project`.
  `renderers/` holds one module per generated file; `markdown.py` is plain
  string-building helpers, not a template engine (D-026); `navigation.py`
  drives the "Related Context" cross-reference footer from a static
  adjacency table (D-030); `writer.py` is the only place that touches disk.
- `generate_knowledge_base(project) -> dict[str, str]` — pure, side-effect
  free. `write_knowledge_base(project, output_dir)` additionally writes to
  disk. Both exported from `generator`.
- Twelve generated files: `OVERVIEW.md`, `PROJECT_STRUCTURE.md`,
  `ARCHITECTURE.md`, `MODULES.md`, `DEPENDENCIES.md`, `API_ROUTES.md`,
  `DATABASE.md`, `AUTHENTICATION.md`, `CONFIGURATION.md`,
  `IMPORTANT_FILES.md`, `AI_CONTEXT.md` (the primary entry point for an AI
  assistant — at-a-glance metrics, recommended reading order, entry points,
  critical files, important directories, and directories already excluded
  from analysis) and `INDEX.md` (table of contents).
- Every file is always generated, even when a category is empty — an empty
  `API_ROUTES.md` says "No API routes detected." rather than not existing
  (D-029), so the file set is fixed and every cross-reference target is
  always valid.
- `cli.py generate [path] [--output DIR]` — runs the full analysis pipeline
  and writes the Knowledge Base; prints the files written.
- 43 new unit tests: every renderer's content, empty and partial
  repositories (no routes / no database / no authentication), determinism
  (identical `Project` → identical output, twice), cross-reference
  integrity (every `Related Context` link target is a real generated file,
  and every generated file has one), a 200-module synthetic repository for
  scale, and writer behaviour (LF line endings, directory creation).

### Notes

- Still no LLM anywhere, still no source code copied into any generated
  file — only extracted facts, never function bodies or file contents.
- Generated Markdown carries no timestamp and is written with forced LF
  line endings, so it is byte-identical across platforms for an unchanged
  repository (D-032).
- Dogfooded against this repository and `sample_repo/`; every generated
  file was reviewed manually as part of this phase's verification.
- Packaging: `generator/` needed its own entry in `pyproject.toml`'s
  `packages.find` include list — the same class of bug D-025 fixed for
  `analyzer.detectors`/`analyzer.intelligence`, caught this time by
  building a real wheel *before* considering the phase done (D-033).

## [0.3.0] — 2026-07-23

Phase 3: the Code Intelligence Engine. Turns an identified `Project` into
structured knowledge of its internal Python architecture — entry points,
import graph, per-module metadata, API routes, database models,
authentication, configuration, module dependencies, and evidence-ranked
important files. Static `ast` analysis only; no source execution, no
inspection of function bodies for business logic.

### Added

- `analyzer/intelligence/` — nine modules (`entrypoints`, `imports`,
  `modules`, `routes`, `database`, `authentication`, `configuration`,
  `relationships`, `importance`), plus `common.py` for shared AST parsing.
  Python only, by design extensible to other languages without changing
  existing modules — see `docs/ARCHITECTURE.md`.
- New models: `EntryPoint`, `ImportEdge`, `ModuleInfo`, `Route`,
  `DatabaseModel`, `ModuleDependency`, `ImportantFile`. `Detection` (from
  Phase 2) is reused for `authentication` and `configuration` rather than
  adding two more bespoke types.
- `Project` gains `entry_points`, `modules`, `imports`, `circular_imports`,
  `routes`, `database_models`, `authentication`, `configuration`,
  `module_dependencies` and `important_files` — all additive, defaulting to
  empty.
- `analyzer.analyze_intelligence()`; `analyzer.analyze_repository()` now
  chains scan → identify → analyze in one call.
- Entry point detection: `if __name__ == "__main__":` guards,
  `FastAPI()`/`Flask()` app objects (with `uvicorn.run()`/`include_router()`
  as corroborating evidence), Django's `manage.py`.
- Import graph with internal/external classification and circular-import
  detection, correctly handling absolute imports, relative imports at any
  nesting depth, and the `from package import name` submodule-vs-attribute
  ambiguity (see Fixed, below).
- Per-module structural metadata: classes, functions, async functions,
  UPPER_CASE constants, exports (`__all__` or public names).
- Route detection for FastAPI/Flask decorators and Django `urls.py`.
- Database model detection for SQLAlchemy (1.x and 2.x styles), Pydantic,
  and Django ORM — model name, table name, fields.
- Authentication detection: JWT, OAuth, API keys, session auth, FastAPI
  `Depends()` correlated to a known security scheme, authentication
  middleware (Starlette-style `add_middleware` and Django's `MIDDLEWARE`).
- Configuration detection: settings modules, `BaseSettings`/`Config`/
  `Settings` classes, `os.environ`/`os.getenv` usage, dotenv usage.
- Evidence-based important-file ranking: entry point presence, import
  fan-in, route/model count and naming convention, each signal capped so no
  single dimension dominates; applies to every Python file, not only ones
  that already have another signal attached.
- CLI `scan` output now includes Entry Points, Backend Routes, Database
  Models, Authentication, Main Configuration, Important Files and
  Dependency Relationships sections; `--json` carries the full structured
  data for every Phase 3 field.
- 44 new unit tests: FastAPI/Flask/Django/CLI applications, malformed
  Python (syntax errors are skipped, never fatal), circular imports, nested
  packages, empty repositories.

### Fixed

- **Import resolution false-positive cycles.** `from package import name`
  was resolving every such import straight to the package's `__init__.py`,
  regardless of whether `name` was actually a submodule. This fabricated
  circular-import reports that don't exist at runtime — caught by
  dogfooding the tool against its own repository, where every detector
  submodule appeared to circularly import `analyzer/detectors/__init__.py`.
  Fixed with two-tier resolution: try `name` as a submodule first, fall
  back to the package's own module file only if no such submodule exists.
- **Packaging silently dropped both Phase 2 and Phase 3 subpackages from
  real builds.** `pyproject.toml`'s explicit `packages = ["analyzer"]` list
  never included `analyzer.detectors` or `analyzer.intelligence` — invisible
  locally because editable installs and pytest's `pythonpath` both bypass
  the packages list, only surfaced by building an actual wheel and
  inspecting its contents. Fixed with `[tool.setuptools.packages.find]`
  auto-discovery.

### Notes

- Still no LLM anywhere. Still no source code is ever executed, imported,
  `eval`'d or `exec`'d — everything is static `ast` analysis.
- Still no new runtime dependencies.
- Absolute import resolution assumes the repository root is the import
  root; `src/`-layout projects under-resolve. A deliberate simplification,
  not a bug — see D-019.

## [0.2.0] — 2026-07-23

Phase 2: the Project Identification Engine. Turns a scanned `Project` into a
repository identity card — languages, frameworks, package managers, build
tools, CI/CD, containerization, environment surfaces, and an overall
classification — from deterministic evidence only.

### Added

- `analyzer/detectors/` — eight detector modules (language, framework,
  package manager, build tool, CI/CD, container, environment, repository
  classifier), each answering one question about a `Project`. See
  `docs/ARCHITECTURE.md`.
- New shared models: `Confidence` (`LOW`/`MEDIUM`/`HIGH`, ordered) and
  `Detection` (name, confidence, evidence) — reused across every detector
  category instead of one bespoke type per category (D-013).
- `Project` gains `languages`, `frameworks`, `package_managers`,
  `build_tools`, `ci_providers`, `container_tools`, `environment_files` and
  `repository_type` — all additive, defaulting to empty/`None` so a bare
  `scan_repository()` result is still a valid `Project`.
- `analyzer.identify_project()` — runs every detector over a scanned
  `Project` and returns it with the results attached.
- `analyzer.analyze_repository()` — `scan_repository()` + `identify_project()`
  in one call; what the CLI and future MCP tools use.
- Framework detection for FastAPI, Django, Flask, Streamlit, Litestar, Sanic
  (Python); React, Next.js, Vue, Nuxt, Express, NestJS, Angular, Svelte
  (JS/TS); Spring Boot (Java); Laravel (PHP); Flutter (Dart).
- Package manager detection for pip, Poetry, uv, Pipenv, npm, Yarn, pnpm,
  Bun, Maven, Gradle, Cargo and Go Modules.
- Build tool detection (Docker, Vite, Turborepo, Nx, Webpack, Rollup), CI/CD
  detection (GitHub Actions, GitLab CI, CircleCI, Jenkins, Azure Pipelines),
  and containerization detection (Docker Compose, Kubernetes, Helm).
- Repository classification into a single, priority-ordered label — Full
  Stack (AI) Web Application, (AI/Machine Learning) REST API, Frontend
  Application, Mobile App, Monorepo, CLI Tool, Python Library, AI Project,
  Machine Learning Project, or Unknown.
- CLI `scan` command now prints an identity card (repository type,
  languages, frameworks, package managers, build tools, CI/CD,
  containerization, environment) before the Phase 1 file statistics, and
  includes the same data in `--json` output.
- 45 new unit tests covering every detector's positive/negative cases,
  confidence levels, hidden-path handling and repository classification.

### Fixed

- `python_dependencies()` (and the equivalent Node/Composer/monorepo checks)
  now read only the repository's root-level manifest, not every matching
  manifest in the tree. A tree-wide search meant a nested fixture's
  dependencies (e.g. `sample_repo/requirements.txt`'s Flask) leaked into the
  root repository's own classification — see D-016.

### Notes

- Still no LLM anywhere. Framework/language/tool detection is entirely
  manifest- and filename-based.
- Still no new runtime dependencies: manifest parsing uses only `tomllib`
  and `json` from the standard library.
- Content reading is now permitted, but only for manifests and well-known
  configuration files (`analyzer/detectors/manifests.py`) — never
  application source code. See D-011.

## [0.1.0] — 2026-07-23

Phase 1: the repository analysis foundation.

### Added

- `analyzer.scan_repository()` — recursive repository scan returning a typed
  `Project`. Prunes ignored directories before descending, so large trees such
  as `node_modules` are never entered.
- Domain models: `FileInfo`, `RepositoryStats`, `Project` — frozen, slotted
  dataclasses forming the engine's public contract.
- Ignore rules in `analyzer/constants.py` covering Python, JavaScript,
  TypeScript, Java, Rust, Go, PHP and Dart ecosystems, plus binary, media,
  archive and build-artefact extensions.
- Repository statistics: file and directory counts, total size, extension
  breakdown ordered by frequency, and the ten largest files.
- Lookup helpers `Project.files_with_extension()` and `Project.find()` for
  later analysis phases.
- CLI: `python cli.py scan <path>` with human-readable and `--json` output,
  plus `--ignore`, `--include-hidden` and `--follow-symlinks`.
- `server.py` placeholder documenting the planned MCP tool surface.
- Test suite covering ignore rules, statistics, determinism, cross-platform
  path handling and error cases.
- Project documentation: `CLAUDE.md`, `README.md`, and `docs/` covering
  architecture, roadmap, decisions, coding standards and contributing.

### Notes

- No language model is used anywhere. All analysis is deterministic and static.
- No runtime dependencies. Standard library only.
- File contents are not read in this phase; the scanner reports facts about
  files, not conclusions about the project.

[Unreleased]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/releases/tag/v0.1.0
