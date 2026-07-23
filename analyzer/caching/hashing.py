"""File hashing with a cheap size+mtime pre-check before touching content.

Hashing every file on every run is exactly the "unnecessary hashing" this
phase asks to avoid — a file whose size and mtime both match the cached
fingerprint is assumed unchanged without reading it (the same fast-path
heuristic make, git and most build systems use). Only a size/mtime
mismatch triggers an actual content read and hash (see
``change_detection.py``, which owns that decision — this module only
knows how to hash, not when to bother).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from analyzer.caching.models import FileFingerprint

_HASH_CHUNK_SIZE = 1 << 20  # 1 MiB


def compute_fingerprint(path: Path) -> FileFingerprint:
    """Stat and hash a file. Used for new files and for files whose
    cached size/mtime no longer match.
    """
    stat = path.stat()
    return FileFingerprint(
        size=stat.st_size, mtime=stat.st_mtime, content_hash=_hash_file(path)
    )


def stat_only(path: Path) -> tuple[int, float]:
    """Size and mtime, without reading content — the cheap fast-path check."""
    stat = path.stat()
    return stat.st_size, stat.st_mtime


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
