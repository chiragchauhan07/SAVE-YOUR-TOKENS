# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Phase 3 — deep analysis (entry points, API routes, database layer). See
[docs/ROADMAP.md](docs/ROADMAP.md).

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

[Unreleased]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/chiragchauhan07/SAVE-YOUR-TOKENS/releases/tag/v0.1.0
