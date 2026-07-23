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

## Phase 2 — Language & Framework Detection

**Goal:** answer "what *is* this repository?"

- [ ] Extension → language mapping, with per-language file and size counts
- [ ] Primary language determination
- [ ] Manifest parsing: `pyproject.toml`, `requirements.txt`, `package.json`,
      `go.mod`, `Cargo.toml`, `pom.xml`, `composer.json`
- [ ] Framework detection via manifest dependencies plus structural signatures
      (Django, Flask, FastAPI, Express, Next.js, React, Vue, Spring, Rails)
- [ ] Confidence scoring — a signal is evidence, not proof
- [ ] Detector registry so new frameworks are additive
- [ ] `Project.languages`, `Project.frameworks`

**Open question:** whether a monorepo needs multiple detected stacks per
project, or one project per workspace package. Decide before implementing.

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
