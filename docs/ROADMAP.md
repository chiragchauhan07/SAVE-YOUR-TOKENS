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
not an aggregation of every nested manifest. Per-workspace-package detail is
deferred; see Phase 3 note below.

**Deliberately excluded:** import-statement scanning (manifest evidence
alone is sufficient and far cheaper — see `docs/DECISIONS.md`), YAML content
parsing (no new dependency; directory/filename convention and substring
checks suffice for Kubernetes/Helm/Flutter), Electron/Tauri/React Native
detection (not in the Phase 2 spec's framework list — candidates for a
future addendum), reading any file's *content* for environment detection
(presence only).

---

## Phase 3 — Deep Analysis

**Goal:** find the parts of a repository an agent asks about first.

- [ ] Entry points: `main.py`, `manage.py`, `index.js`, `Dockerfile` CMD,
      `[project.scripts]`, `package.json` scripts
- [ ] API routes: Django `urls.py`, Flask/FastAPI decorators, Express routers,
      Next.js file-system routing
- [ ] Database layer: ORM models, migration directories, schema files
- [ ] Configuration: `.env.example`, settings modules, env var references
- [ ] Important-file ranking (see below)
- [ ] Dependency graph from import statements
- [ ] Per-workspace-package identification for monorepos: run Phase 2's
      detectors rooted at each workspace member (from `pnpm-workspace.yaml`
      / `package.json` `workspaces`) rather than only the repository root
      (deferred from Phase 2, D-016)

Python is parsed with the standard library `ast`. Other languages start with
conservative signature matching; a real parser is added only when heuristics
prove insufficient.

**Important-file ranking** is the hardest judgement call in the project.
Candidate signals: import fan-in, proximity to entry points, manifest
references, directory conventions, size relative to siblings. Start simple,
measure against real repositories, iterate.

---

## Phase 4 — Context Generation

**Goal:** write the `.ai-context/` pack.

- [ ] Generator per output file (10 files, see README)
- [ ] Pure generators: `Project` in, `str` out
- [ ] Separate writer for filesystem I/O
- [ ] Token budgeting — truncate long lists with explicit counts rather than
      silently
- [ ] `AI_CONTEXT.md` as the condensed index agents read first
- [ ] Golden-file tests against `sample_repo/`

**Guiding constraint:** the reader is a model with a context budget. Prefer
tables and lists over prose. A context pack that is expensive to read defeats
the purpose of the project.

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
