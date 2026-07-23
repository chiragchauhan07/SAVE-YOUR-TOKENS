# Coding Standards

Python 3.11+. Ruff for linting and formatting (`line-length = 88`).

## Typing

Every function is annotated, parameters and return value.

```python
def scan_repository(root: Path | str, *, include_hidden: bool = False) -> Project:
```

- `from __future__ import annotations` at the top of every module.
- Modern syntax: `list[str]`, `str | None`. Not `List`, not `Optional`.
- Return concrete types. `tuple[FileInfo, ...]` tells a caller more than
  `Sequence`, and immutability is part of the contract.
- Accept the widest reasonable input, return the narrowest useful output:
  `Iterable[str]` in, `tuple[str, ...]` out.

## Data

Frozen dataclasses for anything structured:

```python
@dataclass(frozen=True, slots=True)
class FileInfo:
    path: PurePosixPath
    size_bytes: int
    extension: str
```

Never pass a bare `dict[str, Any]` between layers. If it has a shape, give it a
name.

## Paths

`pathlib` everywhere. The single documented exception is `os.walk` in the
scanner (see D-003). Convert to `Path` at the boundary so no raw path string
travels further than the function that produced it.

Relative paths in results are `PurePosixPath`, so output is identical on
Windows and Unix.

## Naming

Names are descriptive, even when long. `repository_root` beats `rr`;
`ignored_directories` beats `ignore`. Loop variables are the exception —
`for file in files` is clear.

Private helpers are `_prefixed` and live below the public function they serve.

## Functions

One responsibility each. A function that walks *and* filters *and* aggregates
should be three functions.

Keyword-only arguments for anything a caller could confuse:

```python
def scan_repository(root, *, include_hidden=False, follow_symlinks=False):
```

No boolean positional arguments, ever.

## Docstrings

Every public function, class and module has one, explaining **why** rather
than restating **what**:

```python
def _describe_file(absolute_path: Path, repository_root: Path) -> FileInfo | None:
    """Build a FileInfo, or None if the file cannot be read.

    Broken symlinks and permission-denied entries are common in real
    repositories and must not abort an otherwise successful scan.
    """
```

Document raised exceptions. Skip docstrings on obvious private one-liners.

## Comments

Comments explain non-obvious decisions:

```python
# In-place assignment is what prunes the walk: os.walk only descends into
# the directories left in this list.
subdirectories[:] = sorted(...)
```

Delete commented-out code. Git remembers.

## Errors

Prefer standard library exceptions where one fits — `FileNotFoundError`,
`NotADirectoryError`, `ValueError`. Add a custom exception only when callers
need to distinguish a case the standard library cannot express.

Error messages name the offending value:

```python
raise FileNotFoundError(f"Repository path does not exist: {resolved}")
```

Never swallow an exception silently. The scanner's `except OSError: return None`
is deliberate and documented — that is the standard to meet.

## Determinism

Non-negotiable. Sort anything that could otherwise vary: directory listings,
file lists, dictionary output. Break ties on a stable key. Never let filesystem
order or hash order reach a result.

## Dependencies

Standard library first. Adding a runtime dependency requires an entry in
`docs/DECISIONS.md` explaining what it does that the standard library cannot.
`analyzer/` currently has zero and should keep them as long as possible.

## Tests

pytest, `tmp_path` for filesystem fixtures. Never touch a real repository or
the network.

- One behaviour per test; the name states the behaviour
- Test the public API, not private helpers
- Assert on values, not on call counts — no mocking the filesystem
- `parametrize` over copy-pasted variants

```python
def test_prunes_ignored_directories(sample_repo):
    project = scan_repository(sample_repo)
    assert not any("node_modules" in str(f.path) for f in project.files)
```

## Module layout

```python
"""Module docstring: what this is and what it is not."""

from __future__ import annotations

import os                        # standard library
from pathlib import Path

from analyzer.constants import IGNORED_DIRECTORIES   # local

_MODULE_CONSTANT = 10

def public_function(...): ...    # public API first

def _helper(...): ...            # private helpers after
```

## What not to do

- No abstract base class with one implementation
- No factory for a single product
- No configuration option nothing varies
- No layer added "for later" — later can add it
- No premature caching; measure first
