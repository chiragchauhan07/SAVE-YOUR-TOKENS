"""Phase 6: incremental re-analysis, reusing cached per-file results
wherever it's safe to (D-044 through D-047).

The public entry point, ``reanalyze()``, returns an up-to-date ``Project``
alongside the ``ChangeSet`` and previous ``Cache`` (if any) that produced
it — the ``incremental`` top-level package uses those to build a
human/AI-facing change report and to decide what to write.
"""

from __future__ import annotations

from pathlib import Path

from analyzer import __version__ as ENGINE_VERSION
from analyzer.caching.cache_io import cache_path, clear_cache, load_cache, save_cache
from analyzer.caching.change_detection import detect_changes
from analyzer.caching.models import (
    CACHE_SCHEMA_VERSION,
    Cache,
    CacheStatus,
    ChangeSet,
    FileFingerprint,
    RenamedFile,
)
from analyzer.caching.reanalysis import build_project_incrementally
from analyzer.models import Project

__all__ = [
    "Cache",
    "CacheStatus",
    "ChangeSet",
    "FileFingerprint",
    "RenamedFile",
    "cache_path",
    "clear_cache",
    "reanalyze",
]


def reanalyze(
    project: Project, cache_file: Path, *, force: bool = False
) -> tuple[Project, ChangeSet, CacheStatus, Cache | None]:
    """Bring Phase 3 intelligence up to date on ``project`` incrementally.

    ``project`` must already have Phase 1/2 fields populated (scan +
    identify already ran — those always run in full; see D-047).

    Returns the updated ``Project``, the detected ``ChangeSet``, why the
    cache was or wasn't trusted, and the previous ``Cache`` itself (for
    diffing in a change report — ``None`` on a first run, a corrupted
    cache, a version mismatch, or ``force=True``). Always writes a fresh,
    valid cache on the way out.
    """
    previous_cache: Cache | None = None
    status = CacheStatus.MISSING
    if not force:
        previous_cache, status = load_cache(cache_file, str(project.root))

    change_set, fingerprints = detect_changes(project, previous_cache)
    updated = build_project_incrementally(project, previous_cache, change_set)

    save_cache(
        cache_file,
        Cache(
            cache_version=CACHE_SCHEMA_VERSION,
            tool_version=ENGINE_VERSION,
            repository_root=str(project.root),
            fingerprints=fingerprints,
            entry_points=updated.entry_points,
            modules=updated.modules,
            routes=updated.routes,
            database_models=updated.database_models,
            imports=updated.imports,
            circular_imports=updated.circular_imports,
            module_dependencies=updated.module_dependencies,
            authentication=updated.authentication,
            configuration=updated.configuration,
            important_files=updated.important_files,
        ),
    )

    return updated, change_set, status, previous_cache
