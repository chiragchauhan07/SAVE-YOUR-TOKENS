# CLAUDE.md

Instructions for Claude Code sessions working on this repository. Read this
before making changes.

## What this project is

**Blueprint** — an MCP server for AI repository context generation.
Formerly released as "Save your Tokens"; renamed in v1.0.0 with no change
to the engine or its guarantees (D-053).

It analyses a software repository **deterministically** (`analyzer/`) and
generates an AI-native Knowledge Base — twelve cross-referenced Markdown
files in `.blueprint/` (`generator/`), this project's primary output —
exposed to AI coding assistants through the Model Context Protocol
(`mcp_server/`). An MCP-compatible coding agent (Claude Code, Cursor, ...)
calls the server or reads the generated files to understand a codebase
quickly, instead of rediscovering its structure by searching from scratch
every session.

It is a **repository intelligence engine**, not a coding agent and not a
replacement for one. Phase 5 made it a production-ready MCP server — this
project's first production-ready release. Phase 6 added an Incremental
Intelligence layer (`analyzer/caching/` + `incremental/`) so repeated
analysis of a mostly-unchanged repository reuses prior work wherever
that's provably safe, always falling back to a full analysis rather than
risk an incorrect result.

## Non-negotiable rules

1. **No LLM in the core.** No Anthropic, OpenAI, Gemini or any other model API
   anywhere in `analyzer/`. Every result is produced by static analysis. If a
   feature seems to need an LLM, it belongs in a future optional layer, not in
   the engine. This constraint is the product, not a limitation.
2. **The engine never depends on anything downstream.** `analyzer/` must not
   import `server.py`, `cli.py`, `generator/`, `mcp_server/`, `incremental/`,
   or any MCP library. The dependency arrow points one way: `analyzer/ <-
   generator/ <- mcp_server/ <- server.py`, and `analyzer/ <- cli.py`,
   `generator/ <- cli.py`, `{analyzer, generator} <- incremental/ <-
   {cli.py, mcp_server/}`. `generator/` may import only `analyzer.models`
   — never `analyzer.scanner`, `analyzer.detectors` or
   `analyzer.intelligence` internals (D-028): it consumes an
   already-fully-populated `Project` and nothing else. `mcp_server/` may
   import only the public APIs of `analyzer/`, `generator/` and
   `incremental/` — never scan, parse an AST, or duplicate any business
   logic (D-041). `incremental/` may import only the public APIs of
   `analyzer/` (including `analyzer.caching`) and `generator/`, and holds
   the orchestration logic neither of those two is allowed to hold itself
   (D-051) — same architectural role `mcp_server/` has, extended to a
   second consumer. `analyzer/caching/` is the one exception to "the
   engine never depends on anything downstream": it is a subpackage of
   the engine, not downstream of it, and is free to call
   `analyzer.intelligence` internals directly (D-044). None of
   `generator/`, `mcp_server/` or `incremental/` re-scans, re-parses, or
   reads a repository file directly beyond what the engine itself already
   does.
3. **Determinism.** Two scans of an unchanged repository must produce identical
   output. Sort before returning. Never let dict or filesystem ordering leak
   into results. An incremental analysis/generation and a full one against
   the same repository state must produce byte-identical output — never
   trade correctness for the speed incremental analysis buys (D-046,
   D-050). When a category can't be proven safe to reuse incrementally,
   fall back to recomputing it in full; never guess that it's still valid.
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
8. **The MCP server never leaks internals to a client.** Every tool in
   `mcp_server/tools.py` catches its own exceptions and returns a safe,
   typed `{"success": false, "error": {...}}` — never a raw exception
   message or a traceback (D-035, confirmed necessary by direct testing:
   FastMCP's own exception wrapping echoes `str(exception)` verbatim). The
   server must never crash on a client-supplied path, and stdout is
   reserved for the protocol stream — logging goes to stderr only, ever
   (D-038).

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
  caching/         Phase 6: incremental re-analysis. A subpackage of the
                    engine, not beside it (D-044) — free to call
                    analyzer.intelligence internals directly.
    hashing.py           FileFingerprint (size, mtime, SHA-256); size+mtime
                         fast path before ever hashing content (D-047).
    change_detection.py  Classifies files new/modified/deleted/unchanged;
                         exact-content-hash rename matching only (D-048).
    reanalysis.py         Reuses cached per-file categories (entry points,
                         modules, routes, database models); always fully
                         recomputes cross-file ones once anything changed
                         (D-046). Selective re-parsing is the `only=`
                         parameter added to five Phase 3 functions (D-045).
    cache_io.py            load/save/clear .blueprint/.cache/cache.json.
                         CacheStatus always fails closed — MISSING, VALID,
                         CORRUPTED, VERSION_MISMATCH, TOOL_VERSION_MISMATCH,
                         CLEARED (D-050). Structured metadata only, never
                         rendered Markdown (D-049).
    __init__.py            reanalyze(project, cache_file, force=False) —
                         the one public entry point.
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
  output.py              DEFAULT_OUTPUT_DIRNAME (".blueprint"),
                       default_output_dir() — resolves the default KB
                       location and migrates a pre-rename ".ai-context/"
                       directory in place, losslessly (D-053).
  writer.py             The only module that touches disk. Forces LF line
                       endings so output is byte-identical cross-platform.
                       write_documents_if_changed() (Phase 6) writes only
                       documents whose rendered content differs from what's
                       already on disk (D-052) — used by incremental/.
  renderers/            One module per generated file, each exposing
                       render(project) -> Document (ai_context.py and
                       index.py additionally take the full document list).
  __init__.py            generate_knowledge_base() (pure) and
                       write_knowledge_base() (writes to disk) orchestrate
                       all twelve renderers.
incremental/       Phase 6: orchestrates analyzer.caching + generator for
                   incremental updates. Top-level package (D-051), same
                   reasoning as generator/ (D-028) and mcp_server/ (D-041)
                   — a consumer spanning both, neither of which may depend
                   on the other directly.
  models.py            CacheInfo, ChangePreview, ChangeReport — this
                       layer's own response types, not discovered facts.
  dependencies.py       DOCUMENT_FIELDS: static document -> Project-field
                       map, used only for ChangeReport reporting, never to
                       gate what gets rendered or written (D-052).
  serialization.py       change_set_dict / change_report_dict / etc. —
                       shared by cli.py's --json output and mcp_server's
                       tool responses (D-034's discipline, extended).
  __init__.py            update_knowledge_base(), preview_changes()
                       (read-only), inspect_cache(), clear_cache().
mcp_server/        Phase 5: expose analyzer/ + generator/ + incremental/
                   over MCP. Top-level package (D-041), same reasoning as
                   generator/ (D-028). An adapter: almost no logic of its
                   own.
  models.py            ErrorType (enum), ToolError — this layer's own
                       response types, not discovered facts.
  errors.py             classify_exception(): maps a caught exception to a
                       safe ToolError. Only place that decides what's safe
                       to tell a client.
  utils.py              build_repository_summary() (shared by two tools —
                       D-036), build_health_status(). No MCP SDK import.
  handlers.py            Pure business logic: calls analyzer.analyze_
                       repository() / generator.generate_knowledge_base() /
                       incremental's update_knowledge_base() etc.
                       No MCP SDK import — testable directly.
  tools.py               The only module that imports the MCP SDK
                       (mcp.server.fastmcp.FastMCP). 6 tools:
                       analyze_repository, repository_summary,
                       generate_knowledge_base (incremental/force params,
                       D-051), health_check, repository_changes,
                       clear_cache. Every tool catches its own exceptions
                       (D-035).
  server.py              Stdio run loop + logging setup (stderr only,
                       D-038).
cli.py             Thin CLI over the engine + generator + incremental.
                   `scan` inspects; `generate` writes the Knowledge Base
                   (always full); `update`/`cache-info`/`cache-clear`
                   (Phase 6) are incremental. Not the product.
server.py          MCP entry point — thin shim over mcp_server/ (D-043),
                   same relationship cli.py has to analyzer/generator.
tests/             pytest, mostly tmp_path; a couple of Phase 5/6 custom
                   fixtures (e.g. incremental_repo in test_mcp_server.py)
                   where repeated multi-file setup earned one.
sample_repo/       Small fake repo for eyeballing CLI output.
docs/              Architecture, roadmap, decisions, standards, MCP_SERVER.md.
```

## Current state

**Phases 1 through 6 are complete.** The engine scans a repository
(Phase 1), identifies what it is — languages, frameworks, package
managers, build tools, CI/CD, containerization, environment surfaces,
overall repository type (Phase 2) — and understands its internal Python
structure: entry points, import graph, module metadata, routes, database
models, authentication, configuration, module dependencies, evidence-
ranked important files (Phase 3). `analyzer.analyze_repository()` is the
one-call composition of all three; `Project` is the contract every later
phase consumes.

The generator (Phase 4) turns that `Project` into the `.blueprint/`
Knowledge Base — twelve cross-referenced Markdown files, this project's
primary output. `blueprint generate <path>` writes it (always a full
regeneration); `generator.generate_knowledge_base(project)` returns it as
`{filename: markdown}` without touching disk.

The MCP server (Phase 5, `mcp_server/`) exposes both over the Model Context
Protocol as six tools (`analyze_repository`, `repository_summary`,
`generate_knowledge_base`, `health_check`, `repository_changes`,
`clear_cache`), stdio transport, using the official MCP Python SDK.
`python server.py` or the installed `blueprint-mcp` console script runs
it. It produces byte-identical Knowledge Bases to the CLI, since both
call the same underlying functions.

The Incremental Intelligence layer (Phase 6, `analyzer/caching/` +
`incremental/`) makes repeated analysis cheap without changing what it
produces: a persistent cache at `.blueprint/.cache/cache.json` tracks
per-file fingerprints and Phase 3 category data; `blueprint update <path>`
(or `generate_knowledge_base(incremental=True)` over MCP) detects what
changed, reuses everything else wherever that's provably safe, and
rewrites only the Knowledge Base documents whose content actually
changed. Any cache problem (missing, corrupted, wrong schema/tool
version) falls back to a full analysis automatically — an incremental run
and a full run against the same repository state are guaranteed to
produce byte-identical output.

The project was rebranded from "Save your Tokens" to **Blueprint** in
v1.0.0 (D-053): the default Knowledge Base directory, console script
names, MCP server identity and one environment variable all changed, with
deprecated aliases/fallbacks kept for a transition period and an
automatic, lossless migration for any pre-rename `.ai-context/` directory.
No internal module, package or class was renamed — only user-facing
surface.

No further phases are currently planned; see `docs/ROADMAP.md` for
possible future work.

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
- Phase 5 uses the official MCP Python SDK (`mcp`) — this project's first
  runtime dependency, scoped to `mcp_server/` only (D-039). `analyzer/` and
  `generator/` stay dependency-free.
- MCP tools never trust the SDK's own exception-to-error conversion for
  safety — every tool catches exceptions itself
  (`mcp_server/errors.py::classify_exception`) and returns a sanitised
  response (D-035).
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
blueprint scan .                  # human summary (or: python cli.py scan .)
blueprint scan . --json           # machine-readable
blueprint generate .              # write .blueprint/ Knowledge Base (always full)
blueprint update .                # incremental regeneration (--force for full)
blueprint cache-info .            # inspect the incremental cache
blueprint cache-clear .           # delete the incremental cache
blueprint-mcp                     # run the MCP server over stdio (or: python server.py)
python -m pytest -q               # test suite
ruff check .                      # lint
mypy analyzer/ generator/ mcp_server/ incremental/ cli.py server.py --ignore-missing-imports
```

## Before you finish a change

- Tests pass.
- New behaviour has a test.
- An architectural choice made along the way is recorded in
  `docs/DECISIONS.md`.
- User-visible changes are in `CHANGELOG.md`.
