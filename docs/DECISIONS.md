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

---

## D-018 — Static analysis only: `ast`, never execution

**Context.** Understanding a repository's real behaviour is easiest by
running it — importing modules, introspecting live objects.

**Decision.** `analyzer/intelligence/` uses only the standard library `ast`
module. Nothing in the target repository is ever imported, `exec`'d,
`eval`'d, or otherwise executed.

**Why.** Executing arbitrary repository code is a code-execution
vulnerability by construction — this tool's whole premise is running
*unattended* over any repository handed to it. It also breaks
determinism (import side effects, network calls, missing dependencies) and
the "no LLM / no execution" philosophy carried from Phase 1.

**Consequence.** Some facts that execution would reveal trivially (the
actual resolved value of a decorator argument built from a function call,
for instance) are simply out of reach. Where `ast` can't determine a fact
confidently, the answer is "not detected", never a guess.

---

## D-019 — Absolute import resolution assumes the repository root is the import root

**Context.** `import a.b.c` / `from a.b import c` need a base directory to
resolve against. Real Python resolves these against `sys.path`, which
depends on how the project is actually run or packaged (plain script,
installed package, `src/` layout with build-tool path injection) —
information this tool cannot obtain without executing the project's own
build configuration.

**Decision.** Absolute imports resolve against the repository root only. A
`src/`-layout project's absolute imports (meant to resolve against `src/`
on `sys.path`) will show as external/unresolved.

**Why.** Guessing the real import root would itself be a guess — exactly
what the philosophy forbids. The root-relative rule is simple, deterministic,
and correct for the common case (flat-layout and most framework-generated
projects).

**Consequence.** `src/`-layout projects under-report internal imports and
module dependencies. Acceptable for now; a future improvement could detect
a `src/` layout from `pyproject.toml`'s own `[tool.setuptools]`/hatchling
configuration (itself declarative, not executed) and try both roots.

---

## D-020 — Django routes are read only from files named `urls.py`

**Context.** Django's `path()`/`re_path()`/`url()` functions could
theoretically appear anywhere.

**Decision.** `routes.py` only inspects files literally named `urls.py`.

**Why.** This is Django's near-universal, framework-enforced convention —
URL configuration lives in `urls.py` modules by design, referenced from
`ROOT_URLCONF`. Scanning every `.py` file for a call named `path` risks
false positives from unrelated code (`pathlib.Path` misuse, a local
variable, an unrelated third-party API). Django doesn't declare an HTTP
method at the URL-conf level either — that's decided by the view's method
handlers, which is behaviour, not structure, so Django routes report
method `"ANY"`.

**Consequence.** A Django project that defines `path()` calls outside a
`urls.py`-named file (unusual, against convention) won't be detected. This
is the right trade-off for precision over recall here.

---

## D-021 — `from package import name` resolves ``name`` as a submodule before falling back to the package's `__init__.py`

**Context.** `from analyzer.detectors import manifests` could mean two
different things: `manifests` is a submodule (`analyzer/detectors/manifests.py`)
or `manifests` is an attribute defined inside `analyzer/detectors/__init__.py`.
An early implementation resolved every such import straight to the
package's `__init__.py`, which fabricated import cycles that don't exist at
runtime — every submodule importing anything from its own package's
`__init__.py`-exposed namespace looked, incorrectly, like it imported the
`__init__.py` itself, and the `__init__.py` importing that submodule closed
a "cycle" that was never really there (found via dogfooding: scanning this
project's own repository reported `detectors/__init__.py` as circularly
importing every one of its own detector submodules).

**Decision.** Resolution is two-tier: try `name` as a submodule of the
target package first (`_resolve_from_name` in `imports.py`); only fall back
to the package's own `__init__.py`/module file if no such submodule exists.

**Why.** This mirrors what CPython's import machinery actually does — `from
package import submodule` imports the submodule (setting it as an attribute
of the partially-initialized package) without re-running `__init__.py`.
Resolving to `__init__.py` unconditionally was a plausible-looking but wrong
static-analysis shortcut, and false-positive circular-import reports are
exactly the kind of unsupported-fact the "never guess" rule exists to
prevent.

**Consequence.** Every `ImportFrom` statement now produces one `ImportEdge`
per imported name (not one per statement) — accurate, but the edge count
for `from x import a, b, c` is 3, not 1. `analyze_imports()`'s docstring and
tests cover this explicitly.

---

## D-022 — Entry points require direct evidence; a conventional filename is corroboration, never sufficient on its own

**Context.** The Phase 3 spec's entry-point examples list filenames
(`main.py`, `app.py`, `run.py`) alongside AST-level signals (`FastAPI()`,
`if __name__ == "__main__":`).

**Decision.** A file is only reported as an entry point when it has direct
AST evidence: an `if __name__ == "__main__":` guard, a `FastAPI()`/`Flask()`
object assignment, or (for Django) is literally named `manage.py`. A
conventional filename alone, with neither, produces no `EntryPoint`.

**Why.** A file named `main.py` with no guard and no framework app object
gives no actual evidence it's ever invoked as a program's starting point —
reporting it anyway would be exactly the kind of guess the philosophy
forbids. Where the filename convention *does* co-occur with real evidence,
it's included as an extra evidence line (not a separate, weaker detection).

**Consequence.** `EntryPoint` has no "weak/filename-only" tier; every
reported entry point is HIGH confidence, because everything reported has
unambiguous supporting evidence by construction.

---

## D-023 — Database model classification requires a specific, qualified base class name

**Context.** `class Foo(Model):` could be Django's `models.Model`,
something else's `Model`, or a project-local base class that happens to be
named `Model`.

**Decision.** Only bases with a resolvable, well-known qualifier are
classified: `models.Model` (Django), `db.Model` (Flask-SQLAlchemy),
`BaseModel` (Pydantic), `Base`/`DeclarativeBase` (SQLAlchemy declarative). A
bare, unqualified `Model` with none of these markers is not classified as
anything.

**Why.** The bare name is genuinely ambiguous without executing the code to
see what it actually resolves to (which this tool never does — D-018).
Reporting a guess here would misrepresent a repository's actual database
layer, which is worse than reporting nothing.

**Consequence.** A codebase with an unconventional import alias (`from
django.db import models as m; class Foo(m.Model)`) won't be detected. This
is an accepted, documented gap — real-world Django code overwhelmingly uses
the `models.Model` convention.

---

## D-024 — Important-file scoring is additive, per-signal-capped, and applies to every Python file

**Context.** Ranking could reward one dominant signal (e.g. raw import
fan-in) or hand-pick "important" names.

**Decision.** `importance.py` sums independent, named signals — entry
point, import fan-in, route count, database-model count, conventional
filename, conventional directory — each capped at 5 points, computed for
every Python file in the repository (not only files that already show up
in some other detector's output).

**Why.** No single signal should dominate (a 50-fan-in utility module
shouldn't automatically outrank a file with three different, meaningful
signals). Scoring every Python file — not just ones with fan-in/routes/
models already attached — matters concretely: a `config.py` nothing yet
imports would otherwise be silently excluded from ranking entirely rather
than scored low. No file name specific to one project is ever
special-cased; every signal is a named, general convention.

**Consequence.** The score is a relative ranking signal, not an absolute
metric — "higher score, more evidence of importance" is the only claim it
makes.

---

## D-025 — Packaging: `packages.find` auto-discovery, not an explicit list

**Context.** `pyproject.toml` listed `packages = ["analyzer"]` explicitly.
Building a real (non-editable) wheel and inspecting its contents during
this phase's verification showed the explicit list silently dropped
`analyzer.detectors` and `analyzer.intelligence` entirely — both subpackages
were missing from the built wheel, though every local test passed, because
editable installs and `pythonpath = ["."]` test discovery both bypass the
`packages` list and read straight from the source tree.

**Decision.** Switched to `[tool.setuptools.packages.find]` with `include =
["analyzer*"]`, which discovers `analyzer` and every subpackage under it
automatically.

**Why.** An explicit list is a maintenance trap: it silently breaks on the
next new subpackage, and nothing in the normal dev loop (editable install,
`pytest`, running `cli.py` directly) would ever catch it — exactly what
happened here across two phases before a real wheel build surfaced it.

**Consequence.** Verifying packaging now requires an actual wheel build
(`python -m build --wheel`), not just an editable install — added to the
release checklist in `docs/CONTRIBUTING.md`'s spirit; do this before any
future package boundary change.
