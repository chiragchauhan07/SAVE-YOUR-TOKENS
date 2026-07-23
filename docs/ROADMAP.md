# Roadmap

Each phase ships something usable. No phase starts before the previous one is
tested and documented.

---

## Phase 1 — Repository Analysis Foundation ✅

**Goal:** turn a path into a structured, filtered, measured `Project`.

- [x] Path validation
- [x] Recursive scan with directory pruning
- [x] Ignore rules for directories, file names and extensions
- [x] `FileInfo`, `RepositoryStats`, `Project` models
- [x] Repository statistics
- [x] CLI (`scan`, human and JSON output)
- [x] Unit tests
- [x] Project documentation

**Deliberately excluded:** reading file contents, detecting anything, MCP.

---

## Phase 2 — Project Identification Engine ✅

**Goal:** answer "what *is* this repository?" — without reading business logic.

- [x] Language detection: extension → language, ordered by byte prevalence
- [x] Manifest reading: `requirements.txt`, `pyproject.toml`, `Pipfile`,
      `package.json`, `composer.json`, `pom.xml`/`build.gradle` (substring)
- [x] Framework detection (Python: FastAPI, Django, Flask, Streamlit,
      Litestar, Sanic · JS/TS: React, Next.js, Vue, Nuxt, Express, NestJS,
      Angular, Svelte · Java: Spring Boot · PHP: Laravel · Dart: Flutter)
- [x] Package manager detection (pip, Poetry, uv, Pipenv, npm, Yarn, pnpm,
      Bun, Maven, Gradle, Cargo, Go Modules)
- [x] Build tool detection (Docker, Vite, Turborepo, Nx, Webpack, Rollup)
- [x] CI/CD detection (GitHub Actions, GitLab CI, CircleCI, Jenkins, Azure
      Pipelines)
- [x] Containerization detection (Docker Compose, Kubernetes, Helm)
- [x] Environment surface detection (`.env.example`/`.template`/`.sample`,
      compose files) — presence only, never content
- [x] Repository classification (Full Stack / REST API / Frontend / Mobile /
      Monorepo / CLI Tool / Python Library / AI Project / Machine Learning
      Project / Unknown), priority-ordered, single label (D-014)
- [x] Confidence + evidence on every `Detection` — never a guess
- [x] `Project.languages`, `.frameworks`, `.package_managers`, `.build_tools`,
      `.ci_providers`, `.container_tools`, `.environment_files`,
      `.repository_type`
- [x] `analyzer.analyze_repository()` — scan + identify in one call
- [x] Unit tests per detector: positive, negative, unknown, conflicting
      evidence, hidden-path handling
- [x] Documentation

**Resolved open question (monorepo stacks):** a scan reports the *root's*
own frameworks/package manager only (D-016) — nested manifests belong to
subprojects and aren't read as evidence about the whole repository. Monorepo
detection is a separate, explicit structural check (workspace config files),
not an aggregation of every nested manifest. Per-workspace-package detail
remains deferred — Phase 3 didn't take it up either, since intelligence
analysis has the identical root-vs-nested-manifest concern (D-019); still
open for whichever future phase needs it.

**Deliberately excluded:** import-statement scanning (manifest evidence
alone is sufficient and far cheaper — see `docs/DECISIONS.md`), YAML content
parsing (no new dependency; directory/filename convention and substring
checks suffice for Kubernetes/Helm/Flutter), Electron/Tauri/React Native
detection (not in the Phase 2 spec's framework list — candidates for a
future addendum), reading any file's *content* for environment detection
(presence only).

---

## Phase 3 — Code Intelligence Engine ✅

**Goal:** understand a repository's internal Python structure — not its
business logic — using deterministic `ast` analysis only.

- [x] Entry points: `if __name__ == "__main__":`, `FastAPI()`/`Flask()` app
      objects (plus `uvicorn.run()`/`include_router()` corroboration),
      Django's `manage.py`
- [x] Import graph: internal vs. external, correctly distinguishing
      submodule imports from package-attribute imports (D-021)
- [x] Circular import detection (DFS over resolved internal edges)
- [x] Per-module metadata: classes, functions, async functions, UPPER_CASE
      constants, exports (`__all__` or public names)
- [x] API routes: FastAPI/Flask decorators (`@app.get(...)`,
      `@app.route(..., methods=[...])`), Django `urls.py` (`path`/`re_path`)
- [x] Database models: SQLAlchemy (1.x `Column`, 2.x `Mapped`), Pydantic
      (`BaseModel`), Django ORM (`models.Model`) — table name and fields
- [x] Authentication detection: JWT, OAuth, API keys, session auth, FastAPI
      `Depends()` (correlated to a known security-scheme variable),
      authentication middleware
- [x] Configuration detection: settings modules, config classes
      (`BaseSettings`/`Config`/`Settings`), environment loading, dotenv usage
- [x] Module dependency relationships, derived from the import graph
- [x] Evidence-based important-file ranking (entry point / fan-in / route /
      model signals + naming convention, every signal capped, applies to
      every Python file — D-024)
- [x] `Project.entry_points`, `.modules`, `.imports`, `.circular_imports`,
      `.routes`, `.database_models`, `.authentication`, `.configuration`,
      `.module_dependencies`, `.important_files`
- [x] `analyzer.analyze_intelligence()`; `analyze_repository()` now chains
      scan → identify → analyze
- [x] 44 new unit tests: FastAPI/Flask/Django/CLI apps, malformed Python
      (syntax errors skipped, never fatal), circular imports, nested
      packages, empty repositories
- [x] Documentation

**Deliberately excluded:** JavaScript/TypeScript route or model detection
(Python only this phase — see `analyzer/intelligence/common.py`'s module
docstring for how a second language slots in later without changing
existing modules), inspecting function/method *bodies* (a route handler's
name is recorded, not what it does), `Express routers`/`Next.js file-system
routing`/`Dockerfile CMD`/`package.json scripts` entry points (JS/TS
scope, deferred with the rest of JS/TS intelligence), migration-directory
and schema-file database detection (ORM model classes only, not raw SQL or
migration history).

**Resolved judgement call (import resolution):** absolute imports resolve
against the repository root only, not a real `sys.path` — a `src/`-layout
project's absolute imports will under-resolve (D-019). Getting this
partially right deterministically was judged better than guessing the real
import root, which the "never guess" philosophy forbids outright.

**Found during this phase, fixed in this phase:** a packaging bug present
since Phase 2 — `pyproject.toml`'s explicit `packages = ["analyzer"]` list
silently dropped `analyzer.detectors` and `analyzer.intelligence` from a
real (non-editable) wheel build, invisible to every local dev workflow
(editable install, `pytest`, running `cli.py` directly). Fixed with
`packages.find` auto-discovery (D-025). A real wheel build is now part of
verifying any future package-boundary change.

---

## Phase 4 — AI Knowledge Base Generator ✅

**Goal:** turn a fully analysed `Project` into a deterministic, cross-referenced
`.ai-context/` Knowledge Base — the project's primary output.

- [x] `generator/` package: one renderer per output file, a pure
      `generate_knowledge_base()` plus a separate `write_knowledge_base()`
      for disk I/O
- [x] Twelve files: `OVERVIEW.md`, `PROJECT_STRUCTURE.md`, `ARCHITECTURE.md`,
      `MODULES.md`, `DEPENDENCIES.md`, `API_ROUTES.md`, `DATABASE.md`,
      `AUTHENTICATION.md`, `CONFIGURATION.md`, `IMPORTANT_FILES.md`,
      `AI_CONTEXT.md` (primary AI entry point), `INDEX.md` (table of contents)
- [x] Every file always generated, with graceful "none detected" content
      when a category is empty (D-029)
- [x] "Related Context" cross-reference footer on every file, driven by a
      static adjacency table (D-030)
- [x] Deterministic output: no timestamps, forced LF line endings across
      platforms (D-032), verified by a same-`Project`-twice equality test
- [x] `cli.py generate` command
- [x] 43 new unit tests: every renderer, empty/partial repositories,
      determinism, cross-reference integrity, a large synthetic repository,
      writer behaviour
- [x] Documentation
- [x] Dogfooded against this repository and `sample_repo/`; output reviewed
      manually

**Deliberately excluded:** a template engine (plain string-building
functions instead — D-026), `MODULES.md` pagination/splitting (one flat
table regardless of repository size — D-027; revisit only once a real large
repository shows this is actually the bottleneck), token-budget truncation
of long lists (every list is already the complete, already-deduplicated
`Project` data; truncating it would contradict "no information should be
discarded").

**Found during this phase, fixed in this phase:** the same packaging bug
class as D-025 — `generator/` is a new top-level package, and
`pyproject.toml`'s `packages.find` include list needed `generator*` added
explicitly or a real wheel build would have silently dropped it again
(D-033). Caught by building an actual wheel before considering the phase
done, not just running the test suite.

---

## Phase 5 — MCP Integration Layer ✅

**Goal:** make the engine and generator callable by any MCP client, as a
thin adapter with no analysis logic of its own. This phase completes the
first production-ready release.

- [x] `mcp_server/` package using the official MCP Python SDK
      (`mcp.server.fastmcp.FastMCP`) — stdio transport
- [x] Four tools: `analyze_repository`, `repository_summary`,
      `generate_knowledge_base`, `health_check`
- [x] `handlers.py` (pure logic, testable without the SDK) / `tools.py`
      (the only module importing the SDK) split — same layering discipline
      as Phases 2 and 3
- [x] Every tool catches its own exceptions and returns a safe, typed
      `{"success": false, "error": {"type": ..., "message": ...}}` rather
      than trusting the SDK's own error wrapping (confirmed unsafe by
      direct testing — see D-035)
- [x] Structured logging to stderr only, `WARNING` by default, `stdout`
      reserved for the protocol stream
- [x] `analyzer/serialization.py` extracted from `cli.py`'s private JSON
      helpers so the CLI and MCP server share one conversion, not two
      (D-034)
- [x] Root `server.py` implemented as a thin shim over `mcp_server/`
- [x] `save-your-tokens-mcp` console script; `mcp` extras dependency group
- [x] 35 new tests: tool registration, every tool's success and error
      paths, sequential-call independence, a real stdio-transport
      subprocess integration test, and a byte-for-byte CLI/MCP output
      parity test
- [x] `docs/MCP_SERVER.md` — installation, Claude Code configuration,
      full tool reference, error types, limitations
- [x] Dogfooded: real wheel build, clean-venv install, real installed
      console script exercised over real stdio transport, generated
      Knowledge Base compared byte-for-byte against the CLI's

**Deliberately excluded:** SSE/streamable-HTTP transport (stdio only —
D-037, though the design doesn't block adding one later), returning
Knowledge Base document content over the wire (statistics only — D-040),
authentication/multi-tenancy (a local single-user server, same trust model
as any other local MCP server a client launches).

**Found and fixed proactively, not reactively this time:** the
`generator/` packaging lesson from Phase 4 (D-033) was applied *before*
writing `mcp_server/`, not discovered after — `mcp_server*` was added to
`pyproject.toml`'s `packages.find` include list before the first wheel
build for this phase, and that build included the package correctly on the
first attempt.

---

## Phase 6 — Incremental Intelligence Engine ✅

**Goal:** turn repeated analysis of a mostly-unchanged repository into
"detect what changed, reuse everything else" — without ever letting a
stale or corrupted cache produce an incorrect result.

- [x] Persistent cache at `.ai-context/.cache/cache.json`: per-file
      fingerprints (size, mtime, SHA-256 content hash) and every Phase 3
      category — structured metadata only, generated Markdown is never
      cached (D-049)
- [x] Deterministic change detection: new / modified / deleted / renamed
      (exact content-hash matching, no fuzzy heuristics — D-048) /
      unchanged, with a size+mtime fast path before any hashing (D-047)
- [x] Selective re-analysis: the four per-file Phase 3 categories (entry
      points, modules, routes, database models) reuse cached results for
      untouched files; the cross-file categories (imports, circular
      imports, module dependencies, authentication, configuration,
      important files) always recompute in full the moment anything
      changed — the engine's own "never sacrifice correctness" boundary
      (D-046), implemented as an additive `only=` parameter on the
      existing Phase 3 functions rather than a parallel code path (D-045)
- [x] Selective generation: every document is still rendered every run;
      only documents whose rendered content actually differs from disk
      are rewritten (D-052) — proven safer than a static per-document
      dependency map by a concrete counterexample
- [x] Cache validation fails closed on every failure mode: missing,
      corrupted JSON, schema-version mismatch, tool-version mismatch —
      always falls back to a full analysis and self-heals the cache
      (D-050)
- [x] Structured `ChangeReport`: files analysed vs. reused, documents
      regenerated vs. unchanged, new/removed routes and models, which
      categories changed, forced-full-analysis flag, duration
- [x] CLI: `update` (`--force` for a full regeneration), `cache-info`,
      `cache-clear`, all with `--json` output; `scan`/`generate` unchanged
      and fully backwards compatible
- [x] MCP: `generate_knowledge_base` gained opt-in `incremental`/`force`
      parameters (default off — no behaviour change for existing
      callers); new `repository_changes` (read-only preview) and
      `clear_cache` tools — both call `incremental/` directly, no
      duplicated logic (D-051)
- [x] `incremental/` — a new top-level package orchestrating
      `analyzer.caching` and `generator`, the same architectural role
      `mcp_server/` already has (D-051)
- [x] Determinism proven across the new axis: an incremental run and a
      forced full run against identical repository state produce
      byte-identical Knowledge Bases
- [x] 51 new tests: every cache-validity and change-kind scenario,
      selective-generation correctness, forced-vs-incremental parity,
      change-report content, CLI and MCP incremental commands
- [x] Documentation
- [x] Dogfooded against this repository: single-file and multi-file
      changes produced exactly the expected selective regeneration; a
      forced full regeneration afterward wrote zero bytes (byte-identical
      to the incremental result); a corrupted cache and a bumped cache
      version both triggered a correct full-analysis fallback

**Deliberately excluded:** honouring `.gitignore` in addition to the
built-in ignore rules (unrelated to incrementality — a Phase 1 scanner
concern, still open), benchmarking on large real-world repositories beyond
this project's own (~90 tracked files) and the synthetic fixtures used in
testing, PyPI release (packaging is verified via wheel build + clean-venv
install every phase, but nothing has been published yet).

---

## Explicitly out of scope for v1

- **Any LLM call in the core.** Determinism is the product.
- Semantic code understanding — this tool maps structure, not meaning.
- Editing or generating application code.
- Analysing remote repositories over the network.

## Possible future work

- Optional LLM enrichment as a clearly separated layer
- Web UI for browsing generated context
- CI integration that keeps `.ai-context/` current on every commit
- Language-server integration for richer symbol data
- Honouring `.gitignore` in the scanner, in addition to the built-in rules
- Benchmarking incremental analysis against large, real-world repositories
- A published PyPI release
