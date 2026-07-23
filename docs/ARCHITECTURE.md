# Architecture

## Principle

The **Analysis Engine (`analyzer/`) is the reusable core.** It discovers
knowledge and never depends on anything downstream. The **Knowledge Base
(`generator/`) is the primary output** — the canonical, AI-native
representation of a repository's structure that the rest of the project
exists to produce. The **MCP Integration Layer (`mcp_server/`) is an
adapter, not a third analysis phase** — it exposes the engine and generator
to AI coding assistants and contains almost no logic of its own. The
**Incremental Intelligence layer (`analyzer/caching/` + `incremental/`) is
a faster path to the same result, never a different one** — it decides
what work can be safely skipped, but every category it can't prove safe to
reuse falls back to exactly the full analysis the other layers already
perform. Everything downstream of the engine and generator (CLI, MCP, a
future web UI) is an interface onto one or both: the analyzer discovers,
the generator organizes, interfaces expose.

```
Repository
    ↓
┌───────────────────────────────────────────┐
│ Analysis Engine  (analyzer/)              │
│                                           │
│   Scanner       → walks, filters, measures│
│   Detectors     → languages, frameworks   │
│   Intelligence  → entry points, routes,   │
│                    models, imports, auth  │
│                                           │
│   Output: Project (typed, frozen)         │
│                                           │
│   analyzer/caching/ — same output,       │
│   reusing prior results where provably   │
│   safe (fingerprints, change detection,  │
│   selective re-analysis)                 │
└───────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────┐
│ Knowledge Base Generator  (generator/)    │
│   Project → .blueprint/ Markdown          │
│   (12 files, cross-referenced — the       │
│    project's primary output)              │
│   write_documents_if_changed() writes     │
│   only documents whose content differs    │
└───────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────┐
│ incremental/  (orchestration)             │
│   update_knowledge_base, preview_changes, │
│   inspect_cache, clear_cache — the only   │
│   caller spanning analyzer/ + generator/  │
└───────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────┐
│ MCP Integration Layer  (mcp_server/)      │
│   6 tools: analyze_repository,            │
│   repository_summary,                     │
│   generate_knowledge_base, health_check,  │
│   repository_changes, clear_cache         │
└───────────────────────────────────────────┘
    ↓
┌──────────┬──────────┬───────────────────┐
│ CLI      │ MCP      │ Future: web, API  │
└──────────┴──────────┴───────────────────┘
    ↓
Claude Code · Cursor · any MCP client
```

## The dependency rule

Dependencies point **inward, one way only**:

```
mcp_server/     ──→ analyzer/, generator/, incremental/  (only their public APIs)
incremental/    ──→ analyzer/ (incl. analyzer.caching), generator/
cli.py          ──→ analyzer/, generator/, incremental/
server.py       ──→ mcp_server/
generator/      ──→ analyzer/models  (nothing else in analyzer/)
analyzer/caching/ ──→ analyzer/ internals (it is analysis, not an adapter — D-044)
analyzer/       ──→ (standard library only)
```

`analyzer/` must never import `cli.py`, `server.py`, `generator/`,
`mcp_server/`, `incremental/`, or any MCP or CLI library —
`analyzer/caching/` is the one exception to "never imports downstream",
because it isn't downstream: it's a subpackage of the engine itself,
free to call `analyzer.intelligence` internals directly (D-044).
`generator/` must never scan a repository, parse an AST, or import
anything from `analyzer/` beyond `analyzer.models` — it consumes an
already-fully-populated `Project` and nothing else (D-028). `incremental/`
may import the public APIs of both `analyzer/` (including
`analyzer.caching.reanalyze`) and `generator/`, and holds the
orchestration logic that spans them — the same architectural role
`mcp_server/` has, extended to a second consumer (D-051). `mcp_server/`
must never scan, parse, or duplicate analysis logic — it calls
`analyzer.analyze_repository()`, `generator.generate_knowledge_base()` and
`incremental`'s four entry points directly and shapes their results
(D-041). Enforcing this is what keeps the engine, the generator, the
incremental orchestrator, and the MCP layer each reusable independently of
the others.

If the MCP layer needs new behaviour, that behaviour goes **into the engine
or the generator** and is called from the adapter. Logic never accumulates
in the adapter — `mcp_server/` stays thin by construction, not by
discipline alone.

## Layers

### 1. Scanner — implemented

**Responsibility:** turn a directory path into a filtered, measured file list.

- Validates the path
- Walks the tree, pruning ignored directories before descending
- Filters ignored file names and extensions
- Collects path, size and extension per file
- Aggregates statistics
- Returns a `Project`

**Explicitly not its job:** opening files, guessing languages, detecting
frameworks. The scanner produces *facts about files*, never *conclusions about
the project*.

### 2. Detectors — implemented

**Responsibility:** turn the file list into conclusions about what the
repository *is*.

Eight independent modules under `analyzer/detectors/`, each answering one
question about a `Project`: what languages, what frameworks, what package
manager, what build tool, what CI provider, what containerization, what
configuration surfaces, and — combining all of the above — what kind of
repository overall. Every answer is a `Detection` (name, `Confidence`,
evidence) or a tuple of them; "unknown" is always a valid result, never an
exception.

Two shared support modules make this data-driven, the same way
`analyzer/constants.py` does for Phase 1's ignore rules:

- `signatures.py` — languages, frameworks, package managers, build tools,
  CI providers and container tooling as data tables. Supporting a new one is
  an entry here, not a new branch in a detector.
- `manifests.py` — the one place allowed to read file *content* (D-011): a
  small engine for reading manifests (`pyproject.toml`, `package.json`,
  ...) and matching them against the signature tables. Also the layer that
  reaches dot-prefixed paths the scanner's default walk excludes
  (`.github/workflows`, `.env.example`) via direct filesystem probes
  (D-012), since the scanner itself is intentionally left unchanged.

`identify_project()` (`detectors/__init__.py`) runs every detector via
direct function calls — no registry, no dynamic discovery (D-015) — and
returns a new `Project` with the results attached. `analyze_repository()`
in `analyzer/__init__.py` composes scanning and identification into one
call.

**Explicitly not its job:** parsing application source code. Reading that
`pyproject.toml` declares `fastapi` is a manifest fact; reading `app.py` to
see how routes are wired is Phase 3's job.

### 3. Intelligence — implemented (Python only)

**Responsibility:** understand a repository's internal Python structure —
never its business logic.

Nine modules under `analyzer/intelligence/`, each answering one question
about a `Project` from `ast`-parsed Python source:

- `entrypoints.py` — where the application starts (`if __name__ ==
  "__main__":`, `FastAPI()`/`Flask()` app objects, Django's `manage.py`)
- `imports.py` — the import graph: internal vs. external, and circular
  imports among internal modules (DFS over resolved internal edges)
- `modules.py` — per-module structural metadata: classes, functions, async
  functions, UPPER_CASE constants, exports (`__all__` or public names)
- `routes.py` — FastAPI/Flask/Django HTTP routes: method, path, handler
- `database.py` — SQLAlchemy, Pydantic and Django ORM models: name, fields,
  table name
- `authentication.py` — JWT, OAuth, API keys, session auth, FastAPI
  `Depends()`, authentication middleware (reuses `Detection`)
- `configuration.py` — settings modules, config classes, environment
  loading, dotenv usage (reuses `Detection`)
- `relationships.py` — reshapes internal import edges into a deduplicated
  module-dependency list
- `importance.py` — evidence-based file ranking (entry point, import
  fan-in, route/model count, naming convention — never a hardcoded name)

Two shared pieces make this possible without duplicating parsing logic:

- `common.py` — `parse_python_files()` (parses every `.py` file once,
  silently skipping syntax errors — D-018) and two small AST-name helpers
  (`simple_name`, `qualifier_name`) reused across five of the modules above.
- `analyzer/detectors/manifests.py` — Phase 3 reuses Phase 2's dependency
  reader (`python_dependencies()`) directly as corroborating evidence in
  `authentication.py`, rather than re-deriving manifest parsing.

`analyze_intelligence()` (`intelligence/__init__.py`) runs every module via
direct function calls (same no-registry choice as Phase 2, D-015) and
returns a new `Project` with the results attached. It must run after
`identify_project()` — route and configuration detection read
`Project.frameworks` and `Project.environment_files`. `analyze_repository()`
composes all three phases (scan → identify → analyze) into one call.

**Hard rules, not just conventions (D-018):** no `import`, `exec`, `eval` or
any other execution of analyzed repository code — everything is `ast`-only,
static analysis. No inspection of function/method *bodies* for business
logic (a route's handler name is recorded; what the handler does is not).
Python only for now; a second language is a new sibling package following
the same one-function-per-concern shape, not a change to this one.

### 4. Generator — implemented

**Responsibility:** turn a fully analysed `Project` into an AI-native
Knowledge Base (`.blueprint/`) — twelve cross-referenced Markdown files.
Never re-scans, re-parses, or re-analyses anything; consumes only
`analyzer.models.Project` (D-028).

```
OVERVIEW.md          Repository type, languages, frameworks, tech stack
PROJECT_STRUCTURE.md File/directory statistics, largest files
ARCHITECTURE.md      Entry points, top important files, dependency summary
MODULES.md           Classes/functions/constants/exports, one row per module
DEPENDENCIES.md      Full import graph, circular imports, external packages
API_ROUTES.md        Detected HTTP routes
DATABASE.md          Detected ORM/schema models
AUTHENTICATION.md    Detected auth mechanisms
CONFIGURATION.md     Settings modules, config classes, env/dotenv usage
IMPORTANT_FILES.md   The complete evidence-ranked file list
AI_CONTEXT.md        Primary entry point: reading order, critical files,
                      entry points, important directories, excluded dirs
INDEX.md             Table of contents for the whole Knowledge Base
```

Three layers, one function per file:

- `renderers/` — one module per generated file, each exposing a single
  `render(project) -> Document` (or, for `ai_context`/`index`, `render(project,
  documents) -> Document` — the only two that need the full document list).
  Pure functions: no filesystem access, trivially unit-testable.
- `markdown.py` — plain string-building helpers (`heading`, `table`,
  `bullet_list`, `detection_table`), not a template engine (D-026).
- `navigation.py` — the "Related Context" cross-reference footer every
  document ends with, driven by a static adjacency table
  (`RELATED_DOCUMENTS`) rather than computed per document (D-030) — same
  "rules as data" principle as `analyzer/constants.py` (D-006).
- `writer.py` — the only place that touches disk. Forces LF line endings so
  output is byte-identical across platforms (D-032).
- `output.py` — `DEFAULT_OUTPUT_DIRNAME` (`.blueprint`) and
  `default_output_dir()`, the one place the default Knowledge Base
  location is computed, shared by the CLI, `incremental/` and
  `mcp_server/`. Also performs the one-time, lossless migration of a
  pre-rename `.ai-context/` directory (D-053).

`generate_knowledge_base(project) -> dict[str, str]` (in `generator/__init__.py`)
is pure and side-effect-free; `write_knowledge_base(project, output_dir)`
additionally writes the files. Kept separate so a future MCP tool can hand
back Knowledge Base content without anything touching the filesystem.

**Every file is always generated**, even when a category is empty — an
absent file is ambiguous, an explicit "No routes detected." is a fact
(D-029). Output is information-dense: tables and bullet lists, not
narrative prose — the reader is a language model with a budget, and Rule 1
of the phase forbids copying source code into any of it.

### 5. MCP Integration Layer — implemented

**Responsibility:** expose the engine and generator over the Model Context
Protocol. A thin adapter — tool definitions, error translation, response
shaping — and nothing else. See [docs/MCP_SERVER.md](MCP_SERVER.md) for
installation, client configuration and the full tool reference.

Four tools (`mcp_server/tools.py`), each calling exactly one `handlers.py`
function:

- `analyze_repository` — the primary tool: analyse, and optionally also
  generate (and optionally write) the Knowledge Base, from one analysis
  pass.
- `repository_summary` — the fast path: analysis only, no generation.
- `generate_knowledge_base` — generate and write the Knowledge Base;
  returns file names and byte counts, never document content (D-040).
- `health_check` — package, MCP SDK and environment versions.

Layered the same way as the previous two phases:

- `handlers.py` — pure business logic, zero MCP SDK imports, callable and
  testable directly. Calls `analyzer.analyze_repository()` and
  `generator.generate_knowledge_base()`/`write_documents()` — never a
  second scan or a second render for one tool call.
- `tools.py` — the only module that imports the MCP SDK
  (`mcp.server.fastmcp.FastMCP`). Every tool wraps its handler call in
  `_run()`, which catches every exception itself rather than trusting
  FastMCP's own error wrapping, confirmed by direct testing to echo a raw
  exception message verbatim (D-035).
- `errors.py` / `models.py` — `classify_exception()` maps a caught
  exception to a small, closed `ErrorType` enum and a safe `ToolError`
  message; nothing about the original exception (beyond the two
  already-safe stdlib cases) reaches a client.
- `utils.py` — `build_repository_summary()` (shared by `analyze_repository`
  and `repository_summary` — D-036) and `build_health_status()`.
- `server.py` — the stdio run loop and logging setup. stdout is reserved
  for the protocol stream; all logging goes to stderr only, `WARNING` by
  default (D-038).

The root `server.py` is a thin shim (`from mcp_server.server import main`),
the same relationship `cli.py` has to `analyzer`/`generator` (D-043).

**Determinism carries through unchanged:** the MCP layer runs the same
`analyze_repository()`/`generate_knowledge_base()` functions the CLI runs,
so a Knowledge Base generated via `generate_knowledge_base` and one
generated via `python cli.py generate` are byte-identical for the same
repository — verified directly in
`tests/test_mcp_server.py::test_mcp_generated_knowledge_base_matches_cli_generated_knowledge_base`.

### 6. Incremental Intelligence — implemented

**Responsibility:** produce the exact same `Project` (and therefore the
exact same Knowledge Base) that a full analysis would, while skipping work
that can be *proven* unnecessary — never work that merely looks
unnecessary. Two packages, split the same way `generator/`/`mcp_server/`
already are:

- `analyzer/caching/` — a subpackage of the engine, not beside it (D-044):
  fingerprinting, change detection and selective re-analysis are analysis,
  entitled to call `analyzer.intelligence` internals directly.
  - `hashing.py` — `FileFingerprint` (size, mtime, SHA-256 content hash);
    a fast size+mtime check before ever reading a file's bytes (D-047).
  - `change_detection.py` — classifies every tracked/untracked file as
    new/modified/deleted/unchanged against the previous cache, then
    matches new+deleted pairs sharing an exact content hash as renames
    (D-048, no fuzzy matching — "never guess").
  - `reanalysis.py` — reuses cached results for the four per-file Phase 3
    categories (entry points, modules, routes, database models); always
    fully recomputes the cross-file ones (imports, circular imports,
    module dependencies, authentication, configuration, important files)
    once anything changed (D-046). Selective re-parsing itself is an
    additive `only=` parameter on the existing Phase 3 functions, not a
    parallel code path (D-045) — one implementation, impossible to drift.
  - `cache_io.py` — load/save/clear `.blueprint/.cache/cache.json`.
    `CacheStatus` is closed (`MISSING`/`VALID`/`CORRUPTED`/
    `VERSION_MISMATCH`/`TOOL_VERSION_MISMATCH`/`CLEARED`); every non-`VALID`
    status fails closed into a full analysis, never a guess (D-050). The
    cache holds structured Phase 3 data only — fingerprints and the same
    frozen dataclasses `Project` already uses — never rendered Markdown
    (D-049).
  - `reanalyze(project, cache_file, *, force=False)` is the one public
    entry point: returns the updated `Project`, the detected `ChangeSet`,
    why the cache was or wasn't trusted, and the previous `Cache` (for
    diffing). Always writes a fresh, valid cache on the way out — even
    after a fallback to full analysis, so the *next* run has something to
    reuse.
- `incremental/` — a new top-level package, the same role `mcp_server/`
  has (D-051): the one place allowed to call both `analyzer.caching` and
  `generator` together.
  - `update_knowledge_base(path, *, output_dir=None, force=False)` — the
    main entry point: reanalyse, render every document, write only the
    ones whose content changed (`generator/writer.py::write_documents_if_changed`,
    D-052 — every document is rendered every run; a static per-document
    dependency map exists only for reporting, never for gating what gets
    rendered or written), return a `ChangeReport`.
  - `preview_changes(path, *, output_dir=None)` — read-only: detects
    changes without writing a cache or the Knowledge Base, for "what would
    an update do" queries.
  - `inspect_cache(path, *, output_dir=None)` / `clear_cache(path, *,
    output_dir=None)` — cache diagnostics and manual invalidation.
  - `dependencies.py::DOCUMENT_FIELDS` — the static document → `Project`-field
    adjacency table, used only to populate `ChangeReport.changed_categories`
    for human/agent readability, never to decide what gets written (D-052).
  - `serialization.py` — `ChangeSet`/`ChangeReport`/`CacheInfo`/
    `ChangePreview` → `dict` conversions, shared verbatim by `cli.py`'s
    `--json` output and `mcp_server/handlers.py`'s tool responses, the
    same "one conversion, not two" discipline as `analyzer/serialization.py`
    (D-034).

**CLI surface:** `update` (`--force` for a full regeneration),
`cache-info`, `cache-clear` — `scan`/`generate` are unchanged.

**MCP surface:** `generate_knowledge_base` gained opt-in
`incremental`/`force` parameters (default off, so existing callers see no
behaviour change); `repository_changes` (read-only preview) and
`clear_cache` are new tools. All three call into `incremental/` directly —
`mcp_server/` still holds zero analysis logic of its own (D-041 extended,
not relaxed).

**Determinism, extended:** an incremental `update_knowledge_base()` call
and a `force=True` call against the same repository state write
byte-identical Knowledge Bases — the same guarantee Phase 4 established
for repeated full generation, now proven to hold across the incremental
axis too (`tests/test_incremental.py::test_force_matches_incremental_result`,
and directly against this repository via dogfooding).

## Data model

`Project` is the contract between every layer. It is a frozen dataclass, so a
scan result is a snapshot that later layers can annotate by construction, not
by mutation.

Currently:

```
Project
├── root: Path                        absolute, resolved
├── name: str
├── files: tuple[FileInfo, ...]       sorted by path            (Phase 1)
├── stats: RepositoryStats                                      (Phase 1)
│   ├── total_files, total_directories, total_size_bytes
│   ├── files_by_extension: dict[str, int]   ordered by frequency
│   └── largest_files: tuple[FileInfo, ...]
├── languages: tuple[LanguageStat, ...]      ordered by prevalence (Phase 2)
├── frameworks: tuple[Detection, ...]                              (Phase 2)
├── package_managers: tuple[Detection, ...]                        (Phase 2)
├── build_tools: tuple[Detection, ...]                             (Phase 2)
├── ci_providers: tuple[Detection, ...]                            (Phase 2)
├── container_tools: tuple[Detection, ...]                         (Phase 2)
├── environment_files: tuple[Detection, ...]                       (Phase 2)
├── repository_type: Detection | None                              (Phase 2)
├── entry_points: tuple[EntryPoint, ...]                           (Phase 3)
├── modules: tuple[ModuleInfo, ...]                                (Phase 3)
├── imports: tuple[ImportEdge, ...]                                (Phase 3)
├── circular_imports: tuple[tuple[str, ...], ...]                  (Phase 3)
├── routes: tuple[Route, ...]                                      (Phase 3)
├── database_models: tuple[DatabaseModel, ...]                     (Phase 3)
├── authentication: tuple[Detection, ...]                          (Phase 3)
├── configuration: tuple[Detection, ...]                           (Phase 3)
├── module_dependencies: tuple[ModuleDependency, ...]              (Phase 3)
└── important_files: tuple[ImportantFile, ...]                     (Phase 3)
```

`Detection` (name, `Confidence`, evidence tuple) is one shared type reused
across every Phase 2 category, and again for Phase 3's `authentication` and
`configuration`, rather than a bespoke class per category (D-013) —
frameworks, package managers, build tools, CI providers, container tooling,
environment surfaces, auth mechanisms and config surfaces are all "I found
X, here's why". `Confidence` is `LOW < MEDIUM < HIGH`.

Phase 3 also introduces types specific enough to need their own shape
(structured fields beyond name/confidence/evidence): `EntryPoint`,
`ImportEdge`, `ModuleInfo`, `Route`, `DatabaseModel`, `ModuleDependency`,
`ImportantFile` — all frozen, slotted dataclasses, same as everything else
in `models.py`.

Later phases extend `Project` with fields for its own concerns. Extension
is additive: existing fields keep their meaning so earlier consumers never
break. Every field beyond `files`/`stats` defaults to empty/`None` until
its phase has run, so a bare `scan_repository()` result remains a valid
`Project`.

## Determinism

A hard requirement, not a nice-to-have.

- Directories and files are visited in sorted order
- The final file list is sorted by path
- Extension counts are sorted by frequency, ties broken by name
- Paths are stored POSIX-style so Windows and Unix scans agree
- No timestamps, absolute host paths or hash seeds leak into results
- Generated Knowledge Base files carry no generation timestamp and are
  written with forced LF line endings, so the same `Project` produces
  byte-identical Markdown regardless of host OS (D-032)
- The MCP layer changes nothing about repository intelligence — it calls
  the same engine and generator functions as the CLI, so the two interfaces
  produce byte-identical Knowledge Bases for the same repository

This makes output diffable, cacheable and testable by equality —
`generate_knowledge_base()` called twice on the same `Project` returns an
identical `dict`, asserted directly in `tests/test_generator.py`.

## Performance

The scanner's one real optimisation is pruning: `os.walk` is given a filtered
subdirectory list in place, so `node_modules` and `.git` are never entered
rather than entered and discarded. On a typical JS repository this is the
difference between thousands of files and hundreds of thousands.

Every layer analyses a repository at most once per call and reuses the
resulting `Project`: `analyzer.analyze_repository()` composes scan → identify
→ intelligence into a single pass; `mcp_server`'s `analyze_repository` tool
reuses that one `Project` for both its summary and (if requested) Knowledge
Base generation, never re-analysing for the second output
(`tests/test_mcp_server.py::test_handle_generate_knowledge_base_analyzes_once_not_twice`
guards this directly).

Phase 6 added the second real optimisation: `analyzer/caching/` avoids
re-parsing Python files whose content hasn't changed since the last run
(a size+mtime check before ever hashing, D-047), and `generator/`'s
`write_documents_if_changed()` avoids rewriting Knowledge Base documents
whose rendered content hasn't changed. Both are pure additions — a call
that never uses the incremental path (`analyzer.analyze_repository()`,
`generator.write_knowledge_base()`, `cli.py generate`) costs exactly what
it always cost. Everything else remains unoptimised, deliberately, until
measurement shows it matters.
