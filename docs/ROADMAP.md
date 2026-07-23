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

## Phase 5 — MCP Server

**Goal:** make the engine callable by any MCP client.

- [ ] Implement `server.py` over stdio
- [ ] Tools: `analyze_repository`, `generate_context`, `get_context`
- [ ] Argument validation and useful error messages
- [ ] Installation and configuration docs for Claude Code and Cursor
- [ ] End-to-end verification against a real client

---

## Phase 6 — Performance & Distribution

- [ ] Cache results keyed by repository state
- [ ] Incremental rescan of changed paths only
- [ ] Honour `.gitignore` in addition to built-in rules
- [ ] Benchmarks on large repositories
- [ ] PyPI release

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
