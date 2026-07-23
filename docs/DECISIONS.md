# Engineering Decisions

A running log of choices that are not obvious from the code, with the reasoning
that produced them. Append new entries; do not rewrite old ones. When a
decision is reversed, add a new entry that supersedes it and say so.

Format: context → decision → consequence.

---

## D-001 — No LLM in the core

**Context.** The obvious way to summarise a repository is to feed it to a
model. Nearly every comparable tool does this.

**Decision.** Version 1 uses no language model anywhere in `analyzer/`. All
output comes from static analysis.

**Why.** Determinism, zero cost, no API key, no network, no rate limits, no
hallucinated file paths, and output that can be cached, diffed and asserted on
in tests. An LLM wrapper would also be trivially reproducible by anyone; a
correct static analyser is not.

**Consequence.** We can never report something requiring semantic
understanding ("this module implements rate limiting"). We report structure and
let the agent infer meaning — which is the thing agents are good at anyway.
Any future LLM layer sits strictly above the engine and stays optional.

---

## D-002 — The engine does not depend on MCP

**Context.** The project is described as an MCP server, so putting the analysis
in the MCP handlers is the shortest path.

**Decision.** All logic lives in `analyzer/`. `server.py` is an adapter.

**Why.** MCP is one delivery mechanism among several we already anticipate
(CLI, web, HTTP API). Coupling analysis to a transport would force a rewrite
for the second interface. It also makes the engine testable without a protocol
harness.

**Consequence.** One extra layer of indirection, and the discipline to resist
putting "just this one thing" in the server.

---

## D-003 — `os.walk` instead of `Path.rglob`

**Context.** `pathlib` is the house style, and `Path.rglob("*")` is the
idiomatic recursive walk.

**Decision.** The scanner uses `os.walk`. This is a deliberate, documented
exception to the pathlib preference.

**Why.** `os.walk` yields a mutable list of subdirectories that can be filtered
in place, which prunes entire subtrees *before descending into them*.
`Path.rglob` has no equivalent — it would enumerate every file in
`node_modules` and then discard them. On a mid-sized JS repository that is the
difference between hundreds of files and hundreds of thousands.

**Consequence.** One `os` import in an otherwise `pathlib` codebase. Paths are
converted to `Path`/`PurePosixPath` at the boundary so nothing downstream sees
raw strings.

---

## D-004 — Frozen dataclasses, not dictionaries

**Context.** Passing dictionaries between layers is faster to write.

**Decision.** Every structured value is a frozen, slotted dataclass.

**Why.** A scan result is a snapshot. Freezing it means later phases annotate
by constructing a new value rather than mutating a shared one, which removes a
whole class of ordering bug. Typed fields also give editors and type checkers
something to work with, and `slots=True` keeps memory sane on large scans.

**Consequence.** Extending `Project` in later phases means changing a class
definition rather than adding a key. That friction is intentional — it forces
the contract to stay explicit.

---

## D-005 — POSIX-style relative paths in results

**Context.** The tool must run on Windows and Unix and produce comparable
output.

**Decision.** `FileInfo.path` is a `PurePosixPath` relative to the repository
root. Only `Project.root` is an absolute, platform-native `Path`.

**Why.** Determinism across platforms. A scan on Windows and the same scan on
Linux now produce identical file lists, so golden-file tests and caches work
everywhere. Relative paths also keep generated context files portable and free
of the developer's home directory.

**Consequence.** Consumers needing an absolute path compose it:
`project.root / file.path`.

---

## D-006 — Ignore rules are data, not logic

**Context.** Ignore decisions could be expressed as predicates in the scanner.

**Decision.** They are frozen sets in `constants.py`; the scanner only consults
them.

**Why.** Supporting a new ecosystem should be a one-line data change reviewable
by anyone, with no risk of altering walk behaviour.

**Consequence.** Rules that genuinely need logic (the `.egg-info` suffix match)
live in the scanner as small named helpers. Keep that list short.

---

## D-007 — `bin/` is not ignored

**Context.** `bin/` appears in most build-output ignore lists.

**Decision.** It is excluded from `IGNORED_DIRECTORIES`.

**Why.** In Python and Node projects `bin/` frequently contains real executable
entry-point scripts, which is exactly what Phase 3 needs to find. Losing entry
points is worse than including a few compiled artefacts, which the extension
filter catches anyway.

**Consequence.** Some C/C++ and Go repositories will include build output.
Revisit if it proves noisy; `--ignore bin` is available meanwhile.

---

## D-008 — Hidden files excluded by default

**Context.** Dot-files include both noise (`.DS_Store`) and genuine signal
(`.env.example`, `.github/workflows`, `.dockerignore`).

**Decision.** Excluded by default, with `--include-hidden` to opt in.
Explicitly ignored names such as `.git` stay ignored either way.

**Why.** The common case is noise, and `.env` files may contain secrets that
should not be enumerated into a context file by accident.

**Consequence.** Phase 2 will need selective access to specific dot-files
(`.github/workflows`, `.env.example`) for CI and configuration detection.
Expect an allowlist of hidden paths rather than a blanket flag flip.

---

## D-009 — `argparse` instead of `click` or `typer`

**Context.** Both are nicer to write against.

**Decision.** Standard library `argparse`.

**Why.** The CLI is a development and inspection tool, not the product. Phase 1
has zero runtime dependencies and that is worth more than nicer help text.

**Consequence.** Revisit if the CLI becomes a shipped surface with many
subcommands.

---

## D-010 — Keyword arguments instead of a `ScanConfig` object

**Context.** Scan options could be bundled into a config dataclass.

**Decision.** `scan_repository` takes keyword-only arguments.

**Why.** Three options do not justify a type. A config object with one
construction site is indirection without benefit.

**Consequence.** If options exceed roughly five, or if the MCP layer starts
passing a config payload straight through, introduce `ScanConfig` then — and
supersede this entry.

---

## D-011 — Detectors may read manifest content; the Phase 1 boundary narrows, not disappears

**Context.** Phase 1's original rule was "no file content is read". Phase 2
framework detection needs to know what's declared in `requirements.txt`,
`pyproject.toml`, `package.json` and similar manifests — presence of a file
name alone can't tell FastAPI from Flask.

**Decision.** `analyzer/detectors/manifests.py` is now the one place allowed
to read file content, and only for package manifests, lockfiles and
well-known configuration files. It never reads application source code —
no AST, no import scanning, no inspection of function bodies.

**Why.** This is metadata, not business logic. Reading `pyproject.toml` to
see that `fastapi` is a dependency is the same category of fact as the
scanner already collects (a file exists, this is its size); it doesn't
require understanding what the code does.

**Consequence.** The boundary that matters going forward is not "Phase 2
touches no content" but "no detector performs source-code semantic
analysis". That stays reserved for Phase 3's parser layer.

---

## D-012 — Detectors probe hidden paths directly; the scanner's filter stays untouched

**Context.** D-008 predicted this: CI configuration (`.github/workflows`,
`.circleci`) and environment templates (`.env.example`) are dot-prefixed, so
the scanner's default walk excludes them entirely — not filtered
after-the-fact, never visited (D-003's directory pruning happens before
`.github` is descended into).

**Decision.** Detectors that need a specific hidden path check the
filesystem directly (`manifests.path_exists`, `manifests.any_files_matching`)
rather than asking the scanner to include all hidden files.

**Why.** `--include-hidden` is all-or-nothing and would reintroduce `.idea`,
`.vscode` and similar noise into every file listing just to reach two
config directories. A targeted probe gets the two paths that matter without
changing what "a scan" returns.

**Consequence.** Detector code has three distinct ways to look for
something (`project.find` for scanned files, `path_exists`/
`any_files_matching` for hidden paths, `read_text` for content) — see the
module docstring in `manifests.py`. This is a real seam to remember when
adding a new hidden-path signal, not a duplication to clean up.

---

## D-013 — One shared `Detection` type, not one per category

**Context.** Frameworks, package managers, build tools, CI providers,
container tooling and environment surfaces all needed the same shape: a
name, a confidence, and the evidence that produced it.

**Decision.** `analyzer.models.Detection` (name, `Confidence`, evidence
tuple) is reused across every detector category instead of defining
`FrameworkMatch`, `PackageManagerMatch`, `CIProviderMatch`, etc.

**Why.** Five near-identical dataclasses would be duplication with no
behavioural difference between them. `Confidence` is an `IntEnum`
(LOW < MEDIUM < HIGH) so `merge_detections()` can pick the strongest
confidence with a plain `max()`.

**Consequence.** A category that later needs a field the others don't
(e.g. a framework's ecosystem) will need its own type at that point — this
is not a permanent guarantee that every category stays identical forever.

---

## D-014 — Repository classification is one priority-ordered label, not a compound tag set

**Context.** The project can be a monorepo, use AI libraries, and have both
a backend and a frontend framework all at once. A tag-set model
(`is_monorepo`, `is_ai`, `has_backend`, ...) would represent that more
completely than a single string.

**Decision.** `repository_classifier.classify_repository()` returns exactly
one `Detection` for the whole repository. Rules run in a fixed priority
order (structural signals like Monorepo and Mobile App first, then
framework composition, then packaging signals, then dependency-only
signals) and the first with evidence wins.

**Why.** A single label is what the CLI's identity card and Phase 4's
generated context actually need to show. A tag set is more information but
also more for a downstream reader to reconcile into one sentence — and
every consumer we can currently name wants the sentence.

**Consequence.** Some genuinely compound repositories will be flattened
losing information (a monorepo that's also AI-flavoured just says
"Monorepo"). If Phase 4 needs the richer picture, add a second,
non-classifying field (e.g. `repository_traits: tuple[str, ...]`) rather
than replacing this one — don't retrofit the single label into a set.

---

## D-015 — Detector orchestration is direct function composition, not a plugin registry

**Context.** Eight detector modules each expose one `detect_*(project)`
function. A `Detector` protocol with a registry (`register(detector)`,
`run_all(project)`) would make the set "pluggable".

**Decision.** `analyzer/detectors/__init__.py::identify_project()` calls
each detector function directly, by name, in a fixed order.

**Why.** There is exactly one call site and detectors aren't dynamically
discovered, loaded from entry points, or user-supplied. A registry here is
indirection with nothing to plug in.

**Consequence.** Adding a detector means one new line in `identify_project`,
not a registration call somewhere else. Revisit if a real plugin use case
appears (e.g. third-party detector packages).

---

## D-016 — Dependency reads are root-manifest-only, not repository-wide

**Context.** `python_dependencies()` initially used `project.find(...)`,
which searches every matching file in the tree. On this project's own
repository, that meant `sample_repo/requirements.txt` (a Flask fixture app)
was read as if it were the root project's own dependency, and the whole
repository was misclassified as "REST API" instead of "CLI Tool".

**Decision.** `python_dependencies`, `node_dependencies`,
`composer_dependencies`, and the monorepo `workspaces` check all read
exactly one file at a fixed root-relative path (`read_text(project,
"pyproject.toml")`, not a tree-wide search).

**Why.** A nested manifest describes a *subproject* — a fixture, an example,
a package inside a monorepo — not the repository as a whole. Only the
Monorepo classification rule is allowed to look past the root, and it does
so explicitly via named marker files, not by aggregating nested manifests.

**Consequence.** A genuine monorepo's per-package frameworks (e.g. a
`packages/api` using FastAPI) won't show up in the root scan's `frameworks`
list — only in a scan rooted at that subpackage. Correct for now; Phase 3
or a later monorepo-aware pass may want to scan and report each workspace
package separately.

---

## D-017 — Docker (build) and Docker Compose (containerization) are different questions

**Context.** The Phase 2 spec listed "Docker" under both Build Systems and
Containerization examples.

**Decision.** `build_detector` reports "Docker" from a `Dockerfile`
(building an image). `container_detector` reports "Docker Compose" from a
compose file (orchestrating containers). Neither module reports the other's
finding.

**Why.** These are genuinely different capabilities a repository can have
independently — a project can build a Docker image with no compose file, or
compose several pre-built images with no Dockerfile of its own. Splitting
them avoids one file signature answering two different questions under one
label.

**Consequence.** A project with both shows "Docker" under Build and "Docker
Compose" under Containerization — two lines, not a merged one. This matches
the identity-card example in the Phase 2 spec exactly.
