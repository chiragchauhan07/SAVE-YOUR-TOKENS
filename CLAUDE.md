# CLAUDE.md

Instructions for Claude Code sessions working on this repository. Read this
before making changes.

## What this project is

**Save your Tokens** — an MCP server for AI repository context generation.

It analyses a software repository **deterministically** (`analyzer/`) and
generates an AI-native Knowledge Base — twelve cross-referenced Markdown
files in `.ai-context/` (`generator/`), this project's primary output. An
MCP-compatible coding agent (Claude Code, Cursor, ...) reads those files to
understand a codebase quickly, instead of rediscovering its structure by
searching from scratch every session.

It is a **repository intelligence engine**, not a coding agent and not a
replacement for one.

## Non-negotiable rules

1. **No LLM in the core.** No Anthropic, OpenAI, Gemini or any other model API
   anywhere in `analyzer/`. Every result is produced by static analysis. If a
   feature seems to need an LLM, it belongs in a future optional layer, not in
   the engine. This constraint is the product, not a limitation.
2. **The engine never depends on anything downstream.** `analyzer/` must not
   import `server.py`, `cli.py`, `generator/`, or any MCP library. The
   dependency arrow points one way: `analyzer/ <- generator/ <- {cli.py,
   server.py}`. `generator/` may import only `analyzer.models` — never
   `analyzer.scanner`, `analyzer.detectors` or `analyzer.intelligence`
   internals (D-028): it consumes an already-fully-populated `Project` and
   nothing else. It never re-scans, re-parses an AST, or reads a repository
   file directly.
3. **Determinism.** Two scans of an unchanged repository must produce identical
   output. Sort before returning. Never let dict or filesystem ordering leak
   into results.
4. **Content reading is metadata/structure-only, never execution.** The Phase
   1 scanner never opens a file. Phase 2 detectors read *manifests*
   (`pyproject.toml`, `package.json`, lockfiles) via
   `analyzer/detectors/manifests.py`. Phase 3's `analyzer/intelligence/`
   parses application Python source with `ast` — but no module in this
   project ever `import`s, `exec`s or `eval`s anything from the analyzed
   repository, and no function/method *body* is inspected for business
   logic (a route handler's name is recorded; what it does is not). See
   D-011, D-018.
5. **Stay in phase.** Do not implement future phases early. Leave a `TODO` or a
   note in `docs/ROADMAP.md` instead.
6. **Never guess.** Every detector attaches confidence and evidence to what it
   reports, and reports nothing when it has neither. "Unknown" / an empty
   result is always valid. A conventional file name alone is never enough —
   it's corroboration for real evidence, not a substitute for it (D-022).
7. **The Knowledge Base never copies source code.** `generator/` renders
   extracted facts (a route's method and path, a model's field names, a
   module's class list) — never a function body, a class implementation, or
   a pasted file. Every generated fact must trace back to a `Project` field;
   nothing in `generator/` invents or infers new information.

## Layout

```
analyzer/          The reusable engine. No MCP, no CLI, no I/O beyond reading.
  constants.py     Phase 1 ignore rules as data.
  models.py        Frozen dataclasses: FileInfo, RepositoryStats, Project,
                    Detection, Confidence, LanguageStat, EntryPoint,
                    ImportEdge, ModuleInfo, Route, DatabaseModel,
                    ModuleDependency, ImportantFile.
  scanner.py       Phase 1: the repository walk.
  utils.py         Small shared helpers.
  detectors/       Phase 2: identify what the scanned repository is.
    signatures.py       Evidence tables as data — languages, frameworks,
                         package managers, build tools, CI, containers.
    manifests.py         Manifest reading + generic evidence-matching engine.
    language_detector.py, framework_detector.py, package_manager_detector.py,
    build_detector.py, cicd_detector.py, container_detector.py,
    environment_detector.py, repository_classifier.py
                         One narrow question each; see each module's docstring.
    __init__.py          identify_project() orchestrates all of the above.
  intelligence/    Phase 3: understand the repository's internal Python
                    structure (never business logic). Python only for now.
    common.py            parse_python_files() + shared AST-name helpers.
    entrypoints.py, imports.py, modules.py, routes.py, database.py,
    authentication.py, configuration.py, relationships.py, importance.py
                         One narrow question each; see each module's docstring.
    __init__.py          analyze_intelligence() orchestrates all of the above;
                         must run after identify_project() (reads Project.
                         frameworks / .environment_files).
generator/         Phase 4: Project -> AI Knowledge Base. Top-level package,
                   NOT nested under analyzer/ (D-028) — a consumer of the
                   engine's output, same architectural role as cli.py.
                   Imports only analyzer.models. Never scans, parses an
                   AST, or reads a repository file directly.
  models.py            Document(filename, title, description, body) — the
                       generator's own output type, not a discovered fact.
  markdown.py          Plain string-building helpers, not a template
                       engine (D-026): heading, table, bullet_list, code,
                       detection_table.
  navigation.py         RELATED_DOCUMENTS: static adjacency table driving
                       every file's "## Related Context" footer (D-030).
  writer.py             The only module that touches disk. Forces LF line
                       endings so output is byte-identical cross-platform.
  renderers/            One module per generated file, each exposing
                       render(project) -> Document (ai_context.py and
                       index.py additionally take the full document list).
  __init__.py            generate_knowledge_base() (pure) and
                       write_knowledge_base() (writes to disk) orchestrate
                       all twelve renderers.
cli.py             Thin CLI over the engine + generator. `scan` inspects;
                   `generate` writes the Knowledge Base. Not the product.
server.py          MCP entry point. Placeholder until Phase 5.
tests/             pytest, no fixtures beyond tmp_path.
sample_repo/       Small fake repo for eyeballing CLI output.
docs/              Architecture, roadmap, decisions, standards.
```

## Current state

**Phase 1 through 4 are complete.** The engine scans a repository (Phase 1),
identifies what it is — languages, frameworks, package managers, build
tools, CI/CD, containerization, environment surfaces, overall repository
type (Phase 2) — and understands its internal Python structure: entry
points, import graph, module metadata, routes, database models,
authentication, configuration, module dependencies, evidence-ranked
important files (Phase 3). `analyzer.analyze_repository()` is the one-call
composition of all three; `Project` is the contract Phase 4 consumes.

The generator (Phase 4) turns that `Project` into the `.ai-context/`
Knowledge Base — twelve cross-referenced Markdown files, this project's
primary output. `python cli.py generate <path>` writes it;
`generator.generate_knowledge_base(project)` returns it as
`{filename: markdown}` without touching disk.

Phase 5 (the MCP server: exposing `analyze_repository()` and the generator
as MCP tools) is next. See `docs/ROADMAP.md`.

## Conventions

- Python 3.11+, full type hints, `from __future__ import annotations`.
- `pathlib` over `os.path`. The one exception is `os.walk` in the scanner,
  which is used because it can prune directories mid-walk and `Path.rglob`
  cannot — see `docs/DECISIONS.md`.
- Frozen dataclasses over dictionaries for anything structured.
- Standard library first. A new runtime dependency needs a decision entry.
  Phase 2 parses TOML (`tomllib`) and JSON (`json`) — both stdlib. No YAML
  parsing dependency: where YAML content matters (Kubernetes manifests,
  `pubspec.yaml`), detectors use directory/filename convention or a plain
  substring check instead (D-011, D-017).
- Detection evidence tables (`analyzer/detectors/signatures.py`) are data,
  not logic — same principle as `analyzer/constants.py` (D-006). Add a new
  language/framework/tool there, not in a detector function.
- Phase 3 parses Python with `ast` (stdlib). No source is ever executed —
  no `import`, `exec`, `eval` of analyzed repository code, ever (D-018).
- Phase 4 builds Markdown with plain string functions
  (`generator/markdown.py`), not a template engine — no new dependency for
  what f-strings and list comprehensions already do clearly (D-026).
- Cross-reference links (`generator/navigation.py::RELATED_DOCUMENTS`) are a
  static adjacency table, same "rules as data" principle as
  `analyzer/constants.py` (D-006) and `analyzer/detectors/signatures.py`.
- Docstrings explain *why*; the code already says *what*.

## Verifying packaging changes

Editable installs (`pip install -e .`) and pytest's `pythonpath = ["."]`
both bypass `pyproject.toml`'s package list and read straight from the
source tree — they will not catch a subpackage silently missing from a real
build (this happened three times: `analyzer.detectors`, `analyzer.intelligence`
and, when `generator/` was added as a new top-level package, `generator`
itself — all three were absent from actual wheels for a full phase before
anyone noticed; see D-025, D-033). Before changing anything under
`[tool.setuptools]`, or after adding a new top-level package or subpackage,
verify with an actual build:

```bash
python -m pip install build -q
python -m build --wheel -o /tmp/dist-check
unzip -l /tmp/dist-check/*.whl   # confirm every subpackage is listed
```

Full detail in `docs/CODING_STANDARDS.md`.

## Working commands

```bash
python cli.py scan .              # human summary
python cli.py scan . --json       # machine-readable
python cli.py generate .          # write .ai-context/ Knowledge Base
python -m pytest -q               # test suite
ruff check .                      # lint
mypy analyzer/ generator/ cli.py server.py --ignore-missing-imports
```

## Before you finish a change

- Tests pass.
- New behaviour has a test.
- An architectural choice made along the way is recorded in
  `docs/DECISIONS.md`.
- User-visible changes are in `CHANGELOG.md`.
