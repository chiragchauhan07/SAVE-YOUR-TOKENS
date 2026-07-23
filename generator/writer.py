"""Deterministic disk output for the Knowledge Base.

Writes exactly the files it's given, nothing more — never clears or owns
the whole output directory, so a `.ai-context/` reused for something else
is not at risk. ``newline="\\n"`` forces LF line endings on every platform;
without it, Windows would translate ``\\n`` to CRLF on write, making
generated output depend on the host OS — a determinism violation exactly
like the one D-005 already ruled out for scan paths.
"""

from __future__ import annotations

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
