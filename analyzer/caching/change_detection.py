"""Deterministic change detection: compare the current repository against
the cached snapshot to produce a ``ChangeSet``.

Fast path: a file whose size and mtime match the cache is assumed
unchanged without hashing it. Only a mismatch triggers an actual content
read and hash (D-045). Renames are detected only as an exact content-hash
match between a deleted path and a new path — no fuzzy/similarity
matching, which would not be deterministic (D-046).
"""

from __future__ import annotations

from pathlib import PurePosixPath

from analyzer.caching.hashing import compute_fingerprint, stat_only
from analyzer.caching.models import Cache, ChangeSet, FileFingerprint, RenamedFile
from analyzer.models import Project


def detect_changes(
    project: Project, cache: Cache | None
) -> tuple[ChangeSet, dict[str, FileFingerprint]]:
    """Compare ``project.files`` against ``cache`` (``None`` means no prior cache).

    Returns the ``ChangeSet`` and the fresh fingerprint map to persist —
    callers save these fingerprints rather than recomputing them.
    """
    cached_fingerprints = cache.fingerprints if cache else {}
    current_paths = {str(file.path) for file in project.files}
    cached_paths = set(cached_fingerprints)

    new_paths = current_paths - cached_paths
    deleted_paths = cached_paths - current_paths
    kept_paths = current_paths & cached_paths

    fresh_fingerprints: dict[str, FileFingerprint] = {}
    modified: list[str] = []
    unchanged_count = 0

    for path_str in sorted(kept_paths):
        absolute = project.root / path_str
        cached = cached_fingerprints[path_str]
        try:
            size, mtime = stat_only(absolute)
        except OSError:
            # Can't stat it right now — treat as modified rather than guess.
            modified.append(path_str)
            continue
        if size == cached.size and mtime == cached.mtime:
            fresh_fingerprints[path_str] = cached
            unchanged_count += 1
            continue
        fingerprint = compute_fingerprint(absolute)
        fresh_fingerprints[path_str] = fingerprint
        if fingerprint.content_hash != cached.content_hash:
            modified.append(path_str)
        else:
            # Touched (mtime changed) but content identical — not a real
            # change; the refreshed fingerprint above avoids re-hashing
            # next time.
            unchanged_count += 1

    new_fingerprints: dict[str, FileFingerprint] = {}
    for path_str in sorted(new_paths):
        absolute = project.root / path_str
        try:
            new_fingerprints[path_str] = compute_fingerprint(absolute)
        except OSError:
            continue
    fresh_fingerprints.update(new_fingerprints)

    deleted_fingerprints = {path: cached_fingerprints[path] for path in deleted_paths}
    renamed, remaining_new, remaining_deleted = _match_renames(
        new_fingerprints, deleted_fingerprints
    )

    change_set = ChangeSet(
        new_files=tuple(sorted(PurePosixPath(p) for p in remaining_new)),
        modified_files=tuple(sorted(PurePosixPath(p) for p in modified)),
        deleted_files=tuple(sorted(PurePosixPath(p) for p in remaining_deleted)),
        renamed_files=tuple(sorted(renamed, key=lambda r: str(r.new_path))),
        unchanged_count=unchanged_count,
    )
    return change_set, fresh_fingerprints


def _match_renames(
    new_fingerprints: dict[str, FileFingerprint],
    deleted_fingerprints: dict[str, FileFingerprint],
) -> tuple[list[RenamedFile], set[str], set[str]]:
    """Exact content-hash matches between new and deleted paths become renames."""
    deleted_by_hash: dict[str, list[str]] = {}
    for path_str, fingerprint in sorted(deleted_fingerprints.items()):
        deleted_by_hash.setdefault(fingerprint.content_hash, []).append(path_str)

    renamed: list[RenamedFile] = []
    remaining_new = set(new_fingerprints)
    remaining_deleted = set(deleted_fingerprints)

    for path_str in sorted(new_fingerprints):
        fingerprint = new_fingerprints[path_str]
        candidates = deleted_by_hash.get(fingerprint.content_hash)
        if not candidates:
            continue
        old_path = candidates.pop(0)
        renamed.append(RenamedFile(PurePosixPath(old_path), PurePosixPath(path_str)))
        remaining_new.discard(path_str)
        remaining_deleted.discard(old_path)

    return renamed, remaining_new, remaining_deleted
