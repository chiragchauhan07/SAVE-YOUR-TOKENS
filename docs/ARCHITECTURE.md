# Architecture

## Principle

The **Analysis Engine is the product.** Every other component is an interface
onto it. MCP is the first such interface, not the centre of the system.

```
Repository
    ↓
┌─────────────────────────────────────────┐
│ Analysis Engine  (analyzer/)            │
│                                         │
│   Scanner   → walks, filters, measures  │
│   Detectors → languages, frameworks     │
│   Parsers   → manifests, routes, models │
│                                         │
│   Output: Project (typed, frozen)       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Context Generator                       │
│   Project → Markdown context files      │
└─────────────────────────────────────────┘
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
cli.py     ──→ analyzer/
server.py  ──→ analyzer/
analyzer/  ──→ (standard library only)
```

`analyzer/` must never import `cli.py`, `server.py`, or any MCP or CLI
library. Enforcing this is what keeps the engine reusable by interfaces that
do not exist yet.

If the MCP layer needs new behaviour, that behaviour goes **into the engine**
and is called from the adapter. Logic never accumulates in the adapter.

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

### 3. Parsers — Phase 3

**Responsibility:** extract structured data from application source itself.

`urls.py` → routes. `models.py` → schema. Entry points, API surfaces,
database layer. This is the first layer permitted to read and parse
*application* code (manifests are already handled in Phase 2 — see D-011).
Each parser targets one format/language and knows nothing about the others.

Python source is parsed with the standard library `ast` module — never with
regular expressions where a real parser exists.

### 4. Generator — Phase 4

**Responsibility:** turn a fully analysed `Project` into Markdown.

One generator per output file. Generators are pure: `Project` in, string out,
no filesystem access. A separate writer handles disk I/O, which keeps
generators trivially testable.

Output must be **information-dense**: tables, bullet lists, deterministic
facts. Not narrative prose. The reader is a language model with a budget.

### 5. MCP Server — Phase 5

**Responsibility:** expose the engine over the Model Context Protocol.

A thin adapter. Tool definitions, argument validation, error translation, and
nothing else.

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
└── repository_type: Detection | None                              (Phase 2)
```

`Detection` (name, `Confidence`, evidence tuple) is one shared type reused
across every Phase 2 category rather than a bespoke class per category
(D-013) — frameworks, package managers, build tools, CI providers,
container tooling and environment surfaces are all "I found X, here's why".
`Confidence` is `LOW < MEDIUM < HIGH`.

Later phases extend `Project` with `entry_points`, `routes`, `database` and
similar fields. Extension is additive: existing fields keep their meaning so
earlier consumers never break. All Phase 2 fields default to empty/`None`
until `identify_project()` has run, so a bare `scan_repository()` result
remains a valid `Project`.

## Determinism

A hard requirement, not a nice-to-have.

- Directories and files are visited in sorted order
- The final file list is sorted by path
- Extension counts are sorted by frequency, ties broken by name
- Paths are stored POSIX-style so Windows and Unix scans agree
- No timestamps, absolute host paths or hash seeds leak into results

This makes output diffable, cacheable and testable by equality.

## Performance

The scanner's one real optimisation is pruning: `os.walk` is given a filtered
subdirectory list in place, so `node_modules` and `.git` are never entered
rather than entered and discarded. On a typical JS repository this is the
difference between thousands of files and hundreds of thousands.

Nothing else is optimised yet, deliberately. Incremental rescanning and caching
are Phase 6, to be added when measurement shows they are needed.
