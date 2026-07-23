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
