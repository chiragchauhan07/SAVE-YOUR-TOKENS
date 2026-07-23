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

### 2. Detectors — Phase 2

**Responsibility:** turn the file list into conclusions.

Each detector is independent, receives a `Project`, and answers one question:
*is this a Django project? a Next.js project? what languages are here?*

Design intent: a registry of detectors, each with a `detect(project)` method
returning a confidence-scored result. Adding a framework means adding a
detector, never editing existing ones.

### 3. Parsers — Phase 3

**Responsibility:** extract structured data from specific file types.

`package.json` → dependencies. `urls.py` → routes. `models.py` → schema.
Parsers are the first layer permitted to read file contents. Each targets one
format and knows nothing about the others.

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
├── root: Path                  absolute, resolved
├── name: str
├── files: tuple[FileInfo, ...] sorted by path
└── stats: RepositoryStats
    ├── total_files, total_directories, total_size_bytes
    ├── files_by_extension: dict[str, int]   ordered by frequency
    └── largest_files: tuple[FileInfo, ...]
```

Later phases extend `Project` with `languages`, `frameworks`, `entry_points`,
`routes` and similar fields. Extension is additive: existing fields keep their
meaning so earlier consumers never break.

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
