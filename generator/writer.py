"""Deterministic disk output for the Knowledge Base.

Writes exactly the files it's given, nothing more — never clears or owns
the whole output directory, so a `.ai-context/` reused for something else
is not at risk. ``newline="\\n"`` forces LF line endings on every platform;
without it, Windows would translate ``\\n`` to CRLF on write, making
generated output depend on the host OS — a determinism violation exactly
like the one D-005 already ruled out for scan paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def write_documents(documents: dict[str, str], output_dir: Path) -> tuple[Path, ...]:
    """Write every document to ``output_dir``, creating it if needed."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename in sorted(documents):
        path = output_dir / filename
        path.write_text(documents[filename], encoding="utf-8", newline="\n")
        written.append(path)
    return tuple(written)


@dataclass(frozen=True, slots=True)
class WriteResult:
    """Which files a selective write actually touched."""

    written: tuple[Path, ...]
    unchanged: tuple[Path, ...]


def write_documents_if_changed(
    documents: dict[str, str], output_dir: Path
) -> WriteResult:
    """Like ``write_documents``, but only touches files whose rendered
    content actually differs from what's already on disk (Phase 6
    selective generation, D-048).

    Always correct by construction: every document is still fully
    rendered first (rendering is pure string formatting — cheap, and the
    only way to know the *true* current content), and the disk write is
    skipped only when a direct content comparison says nothing changed.
    A manually edited or a missing file is handled the same as a
    genuinely stale one — there's no separate "is this file trustworthy"
    state to get out of sync, unlike a cached content hash would be.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    unchanged = []
    for filename in sorted(documents):
        path = output_dir / filename
        content = documents[filename]
        if _matches_existing(path, content):
            unchanged.append(path)
            continue
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)
    return WriteResult(tuple(written), tuple(unchanged))


def _matches_existing(path: Path, content: str) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return handle.read() == content
    except OSError:
        return False
