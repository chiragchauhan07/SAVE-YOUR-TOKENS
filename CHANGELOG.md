# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Phase 2 — language and framework detection. See [docs/ROADMAP.md](docs/ROADMAP.md).

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

[Unreleased]: https://github.com/chirag/save-your-tokens/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/chirag/save-your-tokens/releases/tag/v0.1.0
