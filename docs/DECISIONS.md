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

---

## D-026 — Plain Markdown-building functions, not a template engine

**Context.** `generator/` needed to turn structured data into Markdown.
`templates/` was one of the directory names the Phase 4 brief suggested,
which reads as an invitation to use a templating engine (Jinja2 and
similar).

**Decision.** `generator/markdown.py` is a handful of plain functions
(`heading`, `table`, `bullet_list`, `code`, `detection_table`) building
strings directly. No template files, no templating dependency.

**Why.** Every generated document is a straight, one-pass assembly of
headings, tables and lists from already-structured data — there is no
looping-within-loops, conditional-block, or template-inheritance need that
would justify a templating engine. Adding one would be a new runtime
dependency (breaking the zero-dependency stance carried since Phase 1) for
a problem plain f-strings and list comprehensions already solve clearly.

**Consequence.** If a future phase's output genuinely needs nested,
reusable templates (not just data), revisit this decision explicitly rather
than accreting ad hoc string formatting past the point it stays readable.

---

## D-027 — MODULES.md is one flat table, not paginated or split per file

**Context.** A repository with hundreds or thousands of modules could make
`MODULES.md` very large — "avoid giant monolithic files" is an explicit
Phase 4 principle, and "design an information architecture that scales ...
to enterprise codebases" is an explicit requirement.

**Decision.** `MODULES.md` stays one table, one row per module, in all
cases. No per-file sections, no pagination, no size-based splitting.

**Why.** A table is the most token-dense, scannable representation for
"here is what every module exports" — a heading-per-module layout would be
*more* verbose for the same information, not less. True pagination
(multiple files, an index of ranges) is a real feature with its own design
questions (how many modules per page? by directory? alphabetical?) that
deserves its own decision once a real enterprise-scale repository shows the
single table is actually the bottleneck — not speculatively now.

**Consequence.** A genuinely huge repository will produce a genuinely large
`MODULES.md`. Accepted for this phase; revisit with real data if it becomes
a problem (`ponytail`-style: a known, named limitation, not a silent one).

---

## D-028 — `generator/` is a top-level package, not a subpackage of `analyzer/`

**Context.** `detectors/` and `intelligence/` both live under `analyzer/`.
The Knowledge Base generator could follow that same nesting.

**Decision.** `generator/` is a sibling of `analyzer/`, `cli.py` and
`server.py` — not `analyzer/generator/`.

**Why.** `docs/ARCHITECTURE.md`'s layered diagram drew "Context Generator"
as a box *separate from* "Analysis Engine" from Phase 1 onward, and the
Phase 4 philosophy states the distinction explicitly: "the analyzer
discovers knowledge, the Knowledge Base organizes knowledge." `analyzer/` is
the reusable engine with no I/O beyond reading; `generator/` reads a
`Project` and writes Markdown — a consumer of the engine's output, the same
architectural role as `cli.py`, not part of the engine itself.

**Consequence.** The dependency rule extends cleanly: `generator/` imports
`analyzer.models` (and only `analyzer.models` — no detector or intelligence
internals, since everything it needs is already on `Project`); `analyzer/`
must never import `generator/`, exactly like the existing `cli.py`/`server.py`
rule (D-002).

---

## D-029 — Every Knowledge Base file is always generated, with graceful "none detected" content

**Context.** Many repositories won't have routes, database models, or
authentication. The generator could skip writing those files entirely when
there's nothing to say.

**Decision.** All twelve files are written on every run, regardless of
content. Empty categories render an explicit "No X detected." message
instead of being omitted.

**Why.** A missing file is ambiguous — did the generator check and find
nothing, or did generation simply not cover this category for some other
reason? An explicit "none detected" is itself a fact worth recording, and a
fixed file set is simpler to navigate, link to (D-030's cross-reference
table never needs conditional targets) and test against.

**Consequence.** A CLI-tool repository with no HTTP surface still gets an
`API_ROUTES.md` that says so in one line. This is intentional, not
noise — see Rule "never guess" and Rule 3's "avoid fragmented files": a
present-but-empty file is not fragmentation.

---

## D-030 — Cross-reference links ("Related Context") are a static adjacency table, not computed per document

**Context.** Every generated file needs a "Related Context" footer pointing
to related files (Rule 4). This could be computed dynamically (e.g. "link
to whichever files share data with this one") or declared explicitly.

**Decision.** `generator/navigation.py::RELATED_DOCUMENTS` is a hand-written
`dict[str, tuple[str, ...]]` — same "rules as data" principle as
`analyzer/constants.py` (D-006) and `analyzer/detectors/signatures.py`.

**Why.** The Knowledge Base has a fixed, small set of files (twelve) whose
conceptual relationships don't change per repository — `API_ROUTES.md` is
always related to `AUTHENTICATION.md`, regardless of what any particular
`Project` contains. A computed "relatedness" heuristic would be guessing at
a relationship that a two-line table already states with certainty, for a
graph this size.

**Consequence.** Adding a Knowledge Base file in a future phase means
adding one row to this table (and confirming both directions read sensibly)
— checked by `test_related_context_links_are_valid`, which asserts every
key and value names a file that's actually generated.

---

## D-031 — Environment *file* conventions stay in OVERVIEW.md; CONFIGURATION.md cross-references rather than duplicating

**Context.** Phase 2's `environment_files` (presence of `.env.example` and
similar) and Phase 3's `configuration` (settings modules, config classes,
env-loading calls) are both "configuration" in a loose sense.

**Decision.** `OVERVIEW.md` presents `Project.environment_files` (it's part
of the Phase 2 technology identity card, alongside package managers and
CI/CD). `CONFIGURATION.md` presents `Project.configuration` and adds one
line pointing back to `OVERVIEW.md` for the environment files, rather than
repeating that table.

**Why.** Rule 3 says group closely related information, but also says avoid
fragmented files — it does not say duplicate the same facts under two
headings. Each fact has exactly one canonical location; other files link to
it (this is what "Related Context" and Rule 4's "interconnected graph" are
for).

**Consequence.** An AI reading only `CONFIGURATION.md` sees a pointer, not
the data, for environment files specifically — one hop away via the graph,
by design.

---

## D-032 — Generated files are written with forced LF line endings

**Context.** `Path.write_text()`'s default `newline` behaviour translates
`\n` to the platform line separator on write — CRLF on Windows. The
generator itself already builds content with `\n` only.

**Decision.** `generator/writer.py` passes `newline="\n"` explicitly on
every write.

**Why.** Determinism (Rule 5) means "running the generator twice produces
identical output" — but it should also mean the *same* output regardless of
which OS ran it. Without forcing `newline`, an identical `Project` would
produce byte-different files on Windows versus Linux/macOS, which is the
same class of problem D-005 already ruled out for scanned file paths.

**Consequence.** Generated Markdown is byte-identical across platforms,
which also makes golden-file-style diffing meaningful if a future test
wants it.

---

## D-033 — Packaging: `generator*` added to the auto-discovery include list

**Context.** D-025 fixed `analyzer.detectors`/`analyzer.intelligence` being
silently dropped from real wheel builds by switching to
`[tool.setuptools.packages.find]` with `include = ["analyzer*"]`. That
pattern does not match a new, separate top-level package.

**Decision.** `include = ["analyzer*", "generator*"]`. Verified with an
actual `python -m build --wheel` (not just an editable install) before this
phase's commit — same verification step D-025 established.

**Why.** `generator/` is a top-level package by design (D-028), so it needed
its own discovery pattern; missing this would have reproduced the exact
Phase 2/3 packaging bug for the phase whose whole purpose is being this
project's primary output.

**Consequence.** Any future new top-level package needs the same check:
build a real wheel and confirm its contents before considering the phase
done, not just `pip install -e .`.

---

## D-034 — Shared JSON serialisation extracted into `analyzer/serialization.py`

**Context.** `cli.py`'s `--json` output already converted a `Project` (and
every nested `Detection`, `Route`, `ModuleInfo`, ...) into plain dicts, via
a set of private, module-local functions. The MCP server needs the exact
same conversions for its own tool responses.

**Decision.** Moved those functions verbatim out of `cli.py` into
`analyzer/serialization.py` (`project_to_dict`, `detection_dict`,
`route_dict`, ...). `cli.py` now imports and calls them instead of defining
its own copies; `mcp_server/utils.py` imports the same functions.

**Why.** Phase 5's own instructions are explicit: "reuse existing engines
... never duplicate logic." Two independent implementations of "how does a
`Route` become a dict" would drift the moment one changed without the
other — exactly the kind of duplication this project has avoided since
Phase 1.

**Consequence.** `cli.py --json` output is unchanged (same shape, verified
by the existing test suite still passing after the move — this was a pure
relocation, not a rewrite). Any future consumer needing `Project` as JSON
(a future web UI, for instance) has one place to import from.

---

## D-035 — The MCP layer catches every exception itself; it does not rely on FastMCP's own error wrapping

**Context.** FastMCP catches an exception raised inside a tool function and
re-raises it as `ToolError(f"Error executing tool {name}: {e}")`. Confirmed
by direct testing while designing this phase: that message embeds
`str(e)` — the *original* exception's message — verbatim, with no
sanitisation.

**Decision.** Every tool in `mcp_server/tools.py` wraps its handler call in
`_run()`, which catches `Exception` broadly, calls
`errors.classify_exception()` to produce a safe, typed `ToolError`, and
returns `{"success": False, "error": {...}}` as a normal tool result —
never letting the original exception (or FastMCP's wrapping of it) reach
the client.

**Why.** "Never expose stack traces to clients" is an explicit Phase 5
requirement, and relying on the SDK's own exception handling would mean
trusting `str(exception)` never contains anything sensitive — a bet this
project isn't willing to make, especially since the two exceptions we *do*
pass through verbatim (`FileNotFoundError`, `NotADirectoryError`) are
deliberately checked to be the two cases whose messages are already
hand-authored safe text (`analyzer.utils.validate_repository_path`), not
arbitrary exception content.

**Consequence.** Tool responses have a stable, documented shape
(`{"success": bool, ...}` or `{"success": false, "error": {"type": ...,
"message": ...}}`) regardless of what actually failed — a client can branch
on `success` without needing to know MCP-protocol-level error semantics.
The real exception is still fully logged (with traceback) via
`logging.exception()`, to stderr only, for developer debugging (D-038).

---

## D-036 — `analyze_repository` and `repository_summary` share one response-shaping function

**Context.** Both tools return "a structured summary" of the same kind of
data — project type, languages, frameworks, entry points, routes, database
models, important files, authentication, configuration.

**Decision.** `mcp_server/utils.py::build_repository_summary(project)` is
the one function that shapes this response; both tools' handlers call it.

**Why.** Same "never duplicate logic" principle as D-034, applied within
the MCP layer itself rather than between the MCP layer and the CLI. It also
guarantees the two tools can never silently drift apart in what fields they
expose.

**Consequence.** The important-files list in this summary is capped at 20
entries (`_SUMMARY_IMPORTANT_FILES`) — a deliberate payload-size bound, not
a reflection of a smaller analysis; the complete ranking is always in the
generated `IMPORTANT_FILES.md` (or the full `analyzer.serialization.project_to_dict()`
representation, uncapped, used by `cli.py scan --json`).

---

## D-037 — stdio transport only, for this phase

**Context.** MCP supports several transports (stdio, SSE, streamable HTTP).
Phase 5 explicitly scopes to stdio but asks for a design that "remains
compatible with future MCP transports."

**Decision.** `mcp_server/server.py::main()` calls
`mcp.run(transport="stdio")`. Nothing else in the tool or handler layer
knows or cares which transport is in use.

**Why.** stdio is what every current MCP client (Claude Code, Claude
Desktop, Cursor) launches a local server with, and it's explicitly named as
this phase's required transport. FastMCP's `run()` already accepts
`"stdio" | "sse" | "streamable-http"` as a single parameter — the tool
surface (`tools.py`, `handlers.py`) has zero transport-specific code to
begin with, so adding a transport later is a `server.py` change, not a
redesign.

**Consequence.** No SSE/HTTP testing or configuration in this phase. A
future phase that wants a remote/network transport changes one function
call and adds host/port configuration — everything upstream of `server.py`
is already transport-agnostic.

---

## D-038 — Logging goes to stderr only; stdout is reserved for the protocol

**Context.** On stdio transport, the MCP JSON-RPC stream *is* stdout.
Anything else written there — a stray `print()`, a misconfigured logger —
corrupts every message after it.

**Decision.** `mcp_server/server.py::_configure_logging()` calls
`logging.basicConfig(stream=sys.stderr, ...)` explicitly. No module in
`mcp_server/` ever calls `print()`. Verified directly: running a tool call
with `1>stdout_only.txt 2>stderr_only.txt` showed stdout containing only
the caller's own output, all SDK and application log lines on stderr.

**Why.** This is a correctness requirement, not a style preference — a
server that occasionally prints a debug line to stdout doesn't "log too
much", it silently breaks the protocol for whichever client happens to be
mid-read at that moment. Cheaper to make it structurally impossible than to
rely on every future contributor remembering not to `print()`.

**Consequence.** Default log level is `WARNING` (quiet, per the Phase 5
"support quiet operation" requirement); set
`SAVE_YOUR_TOKENS_LOG_LEVEL=INFO` or `DEBUG` for development visibility —
still to stderr, still safe.

---

## D-039 — The MCP SDK is this project's first runtime dependency

**Context.** `analyzer/` and `generator/` have stayed standard-library-only
since Phase 1 (D-009, D-026, and others). Phase 5 explicitly requires using
the official MCP Python SDK rather than implementing the protocol by hand.

**Decision.** `mcp>=1.0.0` is a dependency of the `mcp_server` package only
— declared in `pyproject.toml`'s `mcp` and `dev` optional-dependency
groups, not the base `dependencies` list. `analyzer/` and `generator/`
still import nothing beyond the standard library.

**Why.** The instruction is explicit and the reasoning is sound
independent of that: implementing JSON-RPC framing, capability negotiation
and the MCP message schema by hand would be a large amount of
protocol-compliance surface to maintain for no benefit over the SDK
Anthropic already publishes and versions for exactly this purpose. This is
categorically different from D-026's "don't add a templating engine for
what f-strings already do" — there is no standard-library equivalent of an
MCP SDK.

**Consequence.** `pip install save-your-tokens` (no extras) still gets a
dependency-free analysis engine and generator; `pip install
save-your-tokens[mcp]` (or `[dev]`) is required to run the MCP server.
`docs/MCP_SERVER.md` documents this distinction for installers.

---

## D-040 — Knowledge Base tools return statistics, never document content

**Context.** `generate_knowledge_base` and `analyze_repository` (when asked
to include the Knowledge Base) could return the full rendered Markdown for
all twelve files inline in the MCP response.

**Decision.** They return file names and byte counts
(`{"files": [...], "total_bytes": ...}`), never the Markdown content
itself. Content only ever reaches disk, via `write_knowledge_base`.

**Why.** Phase 5's own wording is explicit: "return generation statistics."
A large repository's Knowledge Base can run to tens of kilobytes across
twelve files; echoing all of it back through every `generate_knowledge_base`
call would be a needless, repeated allocation and transfer for data the
caller can already read from disk (an AI coding assistant invoking this
tool already has filesystem access to `.ai-context/`) — directly the kind
of "avoid unnecessary allocations" the Performance requirements name.

**Consequence.** A client that wants content, not just confirmation the
Knowledge Base was written, reads the files themselves. If a future use
case genuinely needs content over the wire (a client with no filesystem
access to the analysed repository), that's an additive change — a new
optional flag — not a redesign of this one.

---

## D-041 — `mcp_server/` is a top-level package, following `generator/`'s precedent

**Context.** Same structural question D-028 already answered for
`generator/`: nest under `analyzer/`, or sit alongside it.

**Decision.** `mcp_server/` is a sibling of `analyzer/`, `generator/`,
`cli.py` and `server.py` — not nested under either engine package.

**Why.** `mcp_server/` is an *interface* onto both `analyzer/` and
`generator/` (per the layered diagram: Scanner → Identification →
Intelligence → Generator → **MCP Integration Layer**), architecturally the
same role as `cli.py`, just richer. It imports from both engine packages
but neither imports from it, matching the one-way dependency rule.

**Consequence.** The `pyproject.toml` packaging lesson from D-025/D-033
applied proactively this time — `mcp_server*` was added to
`packages.find`'s include list *before* the first wheel build for this
phase, and that build confirmed the package was included correctly on the
first attempt.

---

## D-042 — Health check reports the installed MCP SDK version, not a hardcoded protocol version string

**Context.** Phase 5 asks the health tool to report "protocol version" among
other fields.

**Decision.** `health_check` reports `mcp_sdk_version` (via
`importlib.metadata.version("mcp")`) instead of a hardcoded MCP protocol
revision string (e.g. a date-versioned spec identifier).

**Why.** The installed SDK version is the one fact this server can verify
at runtime without guessing; a hardcoded protocol-revision string would be
exactly the kind of unsupported, unverifiable claim the "never guess"
principle has ruled out in every previous phase. The SDK version is a
faithful, honest proxy for "what protocol capabilities does this server
actually have" and is what actually helps someone debug an installation —
the stated goal of this tool.

**Consequence.** `package_version` and `server_version` currently report
the same value (`analyzer.__version__`) since there is one project version,
not two independently-versioned components; both fields are kept because
Phase 5 names them separately and a future split (the MCP layer versioned
independently of the engine) would need only implementation, not an API
change.

---

## D-043 — The root `server.py` stays a thin shim; the real implementation lives in `mcp_server/`

**Context.** `server.py` at the repository root has been referenced since
Phase 1 as *the* MCP entry point (`CLAUDE.md`, `README.md`,
`pyproject.toml`'s original `mcp` extras comment all pointed at it).
Phase 5 also asks for a dedicated `mcp_server/` package.

**Decision.** Both exist, in the same relationship as `cli.py` to
`analyzer`/`generator`: root `server.py` is a few lines — `from
mcp_server.server import main` — and is what `[project.scripts]` and
direct `python server.py` invocation both use. All real logic (the FastMCP
instance, tool definitions, handlers, error classification, logging setup)
lives in `mcp_server/`.

**Why.** Preserves every existing reference to "`server.py` is the MCP
entry point" from Phases 1–4 while still satisfying Phase 5's explicit
request for a dedicated package — the two aren't in tension once `server.py`
is understood as the thin launcher, exactly like `cli.py` already is for
the analysis engine.

**Consequence.** `save-your-tokens-mcp` (the installed console script) and
`python server.py` (running from source) are equivalent; both end up
calling `mcp_server.server.main()`.

---

## D-044 — Caching lives inside the engine (`analyzer/caching/`), not beside it

**Context.** Phase 6 needed a place for fingerprinting, change detection and
selective re-analysis. `generator/` and `mcp_server/` are both new
top-level packages sitting *beside* `analyzer/`, each with its own reason
(D-028, D-041) — the obvious pattern to copy.

**Decision.** Caching is a subpackage of the engine, `analyzer/caching/`,
not a new top-level `caching/` package.

**Why.** `generator/` and `mcp_server/` are new top-level packages because
each is a genuinely different *kind* of thing from `analyzer/` — a
renderer, an adapter. Caching isn't a different kind of thing: fingerprint
comparison and selective re-analysis *are* analysis, just an incremental
strategy for producing the same `Project` the full analysis would. It
belongs wherever `analyze_repository()` lives, and must be free to import
`analyzer.intelligence` internals directly (the `only=` parameter threading
in Phase 3's functions) — something D-028 explicitly forbids `generator/`
from doing to `analyzer/`, and the same reasoning would forbid a sibling
`caching/` package from doing it too.

**Consequence.** `analyzer/caching/` can call
`analyzer.intelligence.entrypoints.detect_entry_points(project, only=...)`
directly, as an internal engine collaborator. The public re-analysis entry
point is still just one function, `analyzer.caching.reanalyze()`, so
downstream code never needs to know the module ever changed.

---

## D-045 — Selective re-parsing is an additive `only: frozenset[str] | None` parameter, not a new code path

**Context.** Four Phase 3 functions (`parse_python_files`,
`detect_entry_points`, `analyze_modules`, `detect_routes`,
`detect_database_models`) needed a way to analyse a restricted file subset
instead of every Python file in the repository, without risking a second,
divergent implementation that could drift from the full-analysis one and
silently break the "incremental output equals full output" guarantee.

**Decision.** Each function gained one new keyword-only parameter,
`only: frozenset[str] | None = None`. `None` (the default) preserves the
exact original behaviour — every existing caller, including every Phase
1–5 test, is untouched. When given, `only` restricts parsing/detection to
files whose path string is a member of the set; every other line of logic
— parsing, extraction, sorting — is identical to the full-analysis path,
because it *is* the full-analysis path, just fed fewer files.

**Why.** A parallel "incremental version" of each function would have to
be kept in sync with its full-analysis sibling by hand forever, and any
divergence would be a silent correctness bug — exactly the class of bug
the "byte-identical regardless of path taken" requirement exists to
prevent. One function, one behaviour, an optional filter is the only shape
that can't drift.

**Consequence.** `analyzer/caching/reanalysis.py` calls these functions
with `only=` set to the files that need re-parsing, then merges the fresh
results into the cached ones for files that didn't change (see D-046) —
the merge is `analyzer/caching/`'s responsibility, not a second parsing
mode inside Phase 3 itself.

---

## D-046 — Per-file categories are reused incrementally; cross-file categories always recompute in full

**Context.** Not every Phase 3 category can be correctly reconstructed by
re-parsing only the changed files and reusing everything else. Some
categories (entry points, module metadata, routes, database models) are
purely per-file: one file's result never depends on another file's
content. Others (the import graph, circular-import detection, module
dependencies derived from it, authentication and configuration detection,
which both read repository-wide `Project.frameworks` state) are
inherently cross-file: a change to file A can change what's true about
file B without B itself changing.

**Decision.** Only the four per-file categories are reused incrementally
— cached entries for unaffected files are kept, entries for changed/
deleted files are dropped and replaced with fresh ones, renamed files'
cached entries are relocated to their new path (D-048). Every cross-file
category is always fully recomputed the moment `ChangeSet.has_changes` is
true, with zero attempt at partial reuse. `important_files` (evidence-
ranked, itself a function of import fan-in) is likewise always recomputed
from the merged per-file data.

**Why.** This is the spec's own "never sacrifice correctness — fall back
to full analysis whenever it can't be guaranteed" rule, applied at
category granularity instead of all-or-nothing. Proving a per-file
category safe to reuse is a one-line argument (no cross-file dependency
exists in its detector). Proving a cross-file category safe would require
reconstructing exactly which other files a change could have affected —
correct in principle, but a substantially larger and more fragile piece of
logic for a category of change (an import graph edit) that's usually a
small fraction of total analysis time.

**Consequence.** Incremental analysis is not "everything is incremental" —
it is "the four categories that can be proven safe are incremental, the
rest are recomputed, and recomputing them is still far cheaper than
re-parsing every file from scratch" (files are only re-parsed for the
per-file categories; imports/authentication/configuration derive from the
already-merged `Project`, not from disk again).

---

## D-047 — Change detection: size+mtime first, content hash only when needed

**Context.** Detecting whether a file changed needs to be both correct
(never miss a real change) and cheap (never hash every file on every run —
the spec explicitly calls out avoiding unnecessary hashing).

**Decision.** `FileFingerprint` stores size, mtime and a SHA-256 content
hash. A file is provisionally unchanged if its size and mtime both match
the cached fingerprint; only when either differs is the file actually
opened and hashed. `test_touched_but_unchanged_content_is_not_modified`
covers the inverse case directly — a touched file with byte-identical
content (a `git checkout`-style rewrite) is not treated as modified, since
its mtime changing triggers a rehash whose result then matches the cached
hash.

**Why.** This is the standard git/make-style optimisation: mtime is a
cheap, usually-reliable signal, but never trusted alone, since a rewrite
with unchanged content (or a mtime-preserving copy) must never be
misreported. Hashing is the source of truth; the stat check is purely an
optimisation to avoid paying its cost when nothing could have changed.

**Consequence.** A no-op second run (nothing touched) never opens a single
file's content — a pure `stat()` sweep. A run after an IDE or checkout
operation that rewrites file mtimes without changing content pays one
rehash per touched file, then correctly reports zero modifications.

---

## D-048 — Rename detection is exact content-hash matching only

**Context.** A file that moves without changing content should ideally be
recognised as a rename (reuse its cached analysis at the new path) rather
than as an unrelated delete+add pair (which would force full re-parsing of
"new" content that was never actually new).

**Decision.** After classifying files as new/modified/deleted, every
new file's content hash is compared against every deleted file's cached
hash; an exact match is a `RenamedFile`. No fuzzy matching, similarity
scoring, or partial-content heuristics — "where practical" from the spec
is read here as "deterministically provable", not "best guess".

**Why.** Consistent with "never guess" (Rule 6, `CLAUDE.md`): a fuzzy
rename heuristic could misattribute an unrelated new file to an unrelated
deleted one, silently reusing wrong analysis for a file that only happens
to look similar. An exact hash match has zero false positives by
construction — content did not change, only its path did — and every
correctness guarantee of the per-file merge (D-046) still holds.

**Consequence.** A rename with unchanged content costs zero re-parsing —
the cached per-file entries are relocated to the new path and reused
verbatim. A rename *with* content changes is correctly treated as a
delete+add (new content genuinely needs analysis), not forced into the
rename path.

---

## D-049 — The cache stores structured metadata only, never generated Markdown

**Context.** Phase 6 needed a persistent cache. The most literally "faster"
option would cache the rendered Knowledge Base documents themselves and
serve them back unmodified when nothing relevant changed.

**Decision.** `.ai-context/.cache/cache.json` stores only fingerprints and
Phase 3 category data (the same frozen-dataclass shapes `Project` already
uses, round-tripped through `analyzer/serialization.py`). Rendered
Markdown is never cached; every `update_knowledge_base()` call re-renders
every document from the (possibly-reused) `Project`, every time.

**Why.** Caching rendered output would tie document freshness to whatever
invalidation logic decided to cache it under — exactly the kind of
implicit correctness dependency the spec explicitly rules out ("never
cache generated markdown"). Caching structured facts instead means the
generator (`generator/`) never needs to know incremental analysis exists;
it always receives a complete, correct `Project` and renders normally
(D-028 stays intact — `generator/` gained no new responsibilities).
Selective *writing* (D-052) is what actually avoids redundant disk I/O,
achieved by comparing freshly-rendered content against what's on disk, not
by skipping rendering.

**Consequence.** Rendering the full Knowledge Base costs the same on every
`update_knowledge_base()` call, incremental or not — cheap in practice
(milliseconds, pure string building, no I/O) relative to the analysis it
follows. The only redundant work incremental analysis actually removes is
file parsing and disk writes, not markdown generation.

---

## D-050 — Cache validation always fails closed, never open

**Context.** A persistent cache can go stale in ways beyond "some files
changed": the file can be missing, truncated, hand-edited, written by an
older or newer version of this tool, or point at a repository that moved.

**Decision.** `CacheStatus` is a closed enum — `MISSING`, `VALID`,
`CORRUPTED`, `VERSION_MISMATCH`, `TOOL_VERSION_MISMATCH`, `CLEARED` — and
`load_cache()` never raises; any failure to parse, validate the schema
version (`CACHE_SCHEMA_VERSION`), or validate the tool version
(`analyzer.__version__`) returns `(None, <specific status>)` rather than a
partially-trusted `Cache`. Every one of those statuses is treated
identically downstream: no previous cache, full analysis, a fresh valid
cache written on the way out.

**Why.** The spec is explicit that a stale or damaged cache must never
produce an incorrect result — the only way to guarantee that
unconditionally is for validation to fail closed: any uncertainty about
whether a cached fact is still valid must default to "no, recompute",
never "probably still fine". The specific status is kept (rather than
collapsing straight to a boolean) purely for diagnostics — `cache-info`
and `repository_changes` can tell a user *why* their cache wasn't trusted.

**Consequence.** Upgrading this tool automatically invalidates every
existing cache on next use (tool-version mismatch) rather than risking a
newer analyzer reusing an older version's cached category data, whose
shape or semantics might have changed between versions.

---

## D-051 — `incremental/` is a new top-level package, mirroring `mcp_server/`'s role

**Context.** Orchestrating a full incremental update — detect changes,
reanalyse selectively, regenerate selectively, build a change report — is
logic that spans both `analyzer/` (via `analyzer.caching`) and
`generator/`. Neither existing layer is allowed to depend on the other in
this direction (`generator/` imports only `analyzer.models`, per D-028),
and this orchestration is neither pure analysis nor pure rendering.

**Decision.** A new top-level package, `incremental/`, same architectural
role `mcp_server/` already has (D-028's own reasoning extended): it
imports the public APIs of both `analyzer/` (`analyzer.caching.reanalyze`)
and `generator/` (`generate_knowledge_base`,
`write_documents_if_changed`), and contains the orchestration logic
neither of those two is allowed to hold itself.

**Why.** Keeps the existing dependency rule intact rather than carving an
exception into it — `analyzer/` and `generator/` remain exactly as
independently reusable as they were before Phase 6. The CLI's `update`
command and the MCP server's `generate_knowledge_base`/`repository_changes`/
`clear_cache` tools both call into `incremental/` directly rather than
each reimplementing the same orchestration (mirrors the reasoning behind
`mcp_server`'s own handlers/tools split and `analyzer/serialization.py`'s
extraction in D-034 — one implementation, multiple thin callers).

**Consequence.** `incremental/serialization.py` (dict-building for
`ChangeSet`/`ChangeReport`/`CacheInfo`/`ChangePreview`) is shared verbatim
between `cli.py`'s `--json` output and `mcp_server/handlers.py`'s tool
responses — the same "one conversion, not two" discipline D-034 already
established for `analyzer/serialization.py`.

---

## D-052 — Selective generation compares rendered content against disk, not a static dependency map

**Context.** Deciding which of the twelve Knowledge Base documents to
rewrite after an incremental update needs a way to know which documents a
given change could have affected. The obvious-looking approach is a
static table mapping each document to the `Project` fields it reads
(`incremental/dependencies.py::DOCUMENT_FIELDS` exists and is exactly this
table) and using it to decide which documents to skip re-rendering
entirely.

**Decision.** `DOCUMENT_FIELDS` is used only for the `ChangeReport`'s
human-facing `changed_categories` field — never to gate which documents
get rendered or written. Every document is rendered on every
`update_knowledge_base()` call; `generator/writer.py::write_documents_if_changed`
then compares each freshly-rendered document's content against what's
currently on disk and writes only the ones that actually differ.

**Why.** A concrete test scenario proved the static-map approach would
have been wrong: a file's size changing (with no other structural change)
alters `PROJECT_STRUCTURE.md`'s content (it reports file sizes) even
though `PROJECT_STRUCTURE.md` isn't naturally "about" any single Phase 3
category a dependency map would key on. A static map is a claim about
what *could* affect a document, inferred by a human reading renderer
source — exactly the kind of guess Rule 6 forbids when a cheap, provably
correct alternative exists. Direct content comparison has no such gap: a
document is rewritten if and only if its content actually changed, by
construction, regardless of which `Project` fields fed it.

**Consequence.** Rendering cost is paid for every document on every run
(cheap — see D-049); disk I/O and the resulting `ChangeReport` correctly
reflect exactly what changed, with zero risk of a stale document being
left unwritten because a dependency map missed an indirect relationship.
