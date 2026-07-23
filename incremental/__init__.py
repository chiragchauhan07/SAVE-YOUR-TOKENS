"""Phase 6: incrementally update a repository's Knowledge Base.

The top-level coordinator — the only place that calls into both
``analyzer`` (scan, identify, incremental re-analysis) and ``generator``
(render, selective write). Neither of those packages imports the other or
this one; this package sits on top of both, the same relationship
``mcp_server/`` already has (D-041), extended here rather than duplicated
(D-049).

``update_knowledge_base()`` is, by construction, equivalent to a full
``analyze_repository()`` + ``write_knowledge_base()`` whenever nothing can
safely be reused (``force=True``, a missing cache, or an invalid one) — the
same underlying engine and generator functions run either way; the only
difference is how much work gets skipped.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeVar

from analyzer import identify_project, scan_repository
from analyzer.caching import Cache, CacheStatus, ChangeSet, cache_path, reanalyze
from analyzer.caching import clear_cache as _clear_cache_file
from analyzer.caching.cache_io import load_cache
from analyzer.caching.change_detection import detect_changes
from analyzer.models import Project
from generator import generate_knowledge_base
from generator.writer import WriteResult, write_documents_if_changed
from incremental.models import CacheInfo, ChangePreview, ChangeReport

_T = TypeVar("_T")

__all__ = [
    "CacheInfo",
    "ChangePreview",
    "ChangeReport",
    "clear_cache",
    "inspect_cache",
    "preview_changes",
    "update_knowledge_base",
]

_TRACKED_FIELDS = (
    "entry_points",
    "modules",
    "imports",
    "circular_imports",
    "routes",
    "database_models",
    "authentication",
    "configuration",
    "module_dependencies",
    "important_files",
)


def preview_changes(
    path: str | Path, *, output_dir: str | Path | None = None
) -> ChangePreview:
    """What would change on the next ``update_knowledge_base`` call.

    Read-only: detects changes against the cache but never writes a new
    cache or touches the Knowledge Base — for "what changed" queries that
    shouldn't have side effects.
    """
    root = Path(path).expanduser().resolve()
    resolved_output = _resolve_output_dir(root, output_dir)
    cache_file = cache_path(resolved_output)

    project = identify_project(scan_repository(root))
    cache, status = load_cache(cache_file, str(root))
    change_set, _fingerprints = detect_changes(project, cache)
    return ChangePreview(cache_status=status, change_set=change_set)


def update_knowledge_base(
    path: str | Path, *, output_dir: str | Path | None = None, force: bool = False
) -> ChangeReport:
    """Incrementally analyse ``path`` and update its Knowledge Base."""
    started = time.monotonic()
    root = Path(path).expanduser().resolve()
    resolved_output = _resolve_output_dir(root, output_dir)
    cache_file = cache_path(resolved_output)

    project = identify_project(scan_repository(root))
    updated, change_set, status, previous_cache = reanalyze(
        project, cache_file, force=force
    )

    documents = generate_knowledge_base(updated)
    write_result = write_documents_if_changed(documents, resolved_output)

    return _build_report(
        change_set=change_set,
        status=status,
        updated=updated,
        previous_cache=previous_cache,
        write_result=write_result,
        duration=time.monotonic() - started,
        forced=force,
    )


def inspect_cache(
    path: str | Path, *, output_dir: str | Path | None = None
) -> CacheInfo:
    """Report the cache's own state without changing anything."""
    root = Path(path).expanduser().resolve()
    resolved_output = _resolve_output_dir(root, output_dir)
    cache_file = cache_path(resolved_output)
    cache, status = load_cache(cache_file, str(root))
    return CacheInfo(
        exists=cache_file.is_file(),
        valid=cache is not None,
        status=status,
        path=str(cache_file),
        cache_version=cache.cache_version if cache else None,
        tool_version=cache.tool_version if cache else None,
        tracked_files=len(cache.fingerprints) if cache else 0,
    )


def clear_cache(path: str | Path, *, output_dir: str | Path | None = None) -> bool:
    """Delete the cache, forcing the next update to start fresh. Returns
    whether a cache file was actually present to remove.
    """
    root = Path(path).expanduser().resolve()
    resolved_output = _resolve_output_dir(root, output_dir)
    return _clear_cache_file(cache_path(resolved_output))


def _resolve_output_dir(root: Path, output_dir: str | Path | None) -> Path:
    if output_dir is None:
        return root / ".ai-context"
    return Path(output_dir).expanduser().resolve()


def _build_report(
    *,
    change_set: ChangeSet,
    status: CacheStatus,
    updated: Project,
    previous_cache: Cache | None,
    write_result: WriteResult,
    duration: float,
    forced: bool,
) -> ChangeReport:
    files_analyzed = len(change_set.files_to_reparse)
    total_py_files = len(updated.files_with_extension(".py"))
    files_reused = max(total_py_files - files_analyzed, 0)

    new_routes, removed_routes = _diff_by_key(
        (previous_cache.routes if previous_cache else ()),
        updated.routes,
        key=lambda route: f"{route.method} {route.path}",
    )
    new_models, removed_models = _diff_by_key(
        (previous_cache.database_models if previous_cache else ()),
        updated.database_models,
        key=lambda model: model.name,
    )

    return ChangeReport(
        cache_status=status,
        change_set=change_set,
        files_analyzed=files_analyzed,
        files_reused=files_reused,
        documents_regenerated=tuple(sorted(path.name for path in write_result.written)),
        documents_unchanged=tuple(sorted(path.name for path in write_result.unchanged)),
        new_routes=new_routes,
        removed_routes=removed_routes,
        new_models=new_models,
        removed_models=removed_models,
        changed_categories=_changed_categories(previous_cache, updated),
        duration_seconds=duration,
        forced_full_analysis=forced or status != CacheStatus.VALID,
    )


def _diff_by_key(
    old: Iterable[_T], new: Iterable[_T], *, key: Callable[[_T], str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    old_keys = {key(item) for item in old}
    new_keys = {key(item) for item in new}
    return tuple(sorted(new_keys - old_keys)), tuple(sorted(old_keys - new_keys))


def _changed_categories(
    previous_cache: Cache | None, updated: Project
) -> tuple[str, ...]:
    if previous_cache is None:
        return _TRACKED_FIELDS
    return tuple(
        field
        for field in _TRACKED_FIELDS
        if getattr(previous_cache, field) != getattr(updated, field)
    )
