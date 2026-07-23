"""Output types for the incremental update layer — not discovered facts.

Like every other layer's own ``models.py`` in this project, these are
presentation/reporting types specific to this package, not general
analysis facts (which stay in ``analyzer.models``) and not cache internals
(which stay in ``analyzer.caching.models``).
"""

from __future__ import annotations

from dataclasses import dataclass

from analyzer.caching.models import CacheStatus, ChangeSet


@dataclass(frozen=True, slots=True)
class CacheInfo:
    """A snapshot of the cache's own state, for inspection tooling."""

    exists: bool
    valid: bool
    status: CacheStatus
    path: str
    cache_version: int | None
    tool_version: str | None
    tracked_files: int


@dataclass(frozen=True, slots=True)
class ChangePreview:
    """What would change on the next update — read-only, no side effects."""

    cache_status: CacheStatus
    change_set: ChangeSet


@dataclass(frozen=True, slots=True)
class ChangeReport:
    """A human- and AI-facing summary of one incremental update."""

    cache_status: CacheStatus
    change_set: ChangeSet
    #: Python files freshly AST-parsed this run.
    files_analyzed: int
    #: Python files whose cached per-file results were reused unparsed.
    files_reused: int
    #: Knowledge Base filenames actually rewritten (content differed).
    documents_regenerated: tuple[str, ...]
    #: Knowledge Base filenames left untouched (content identical).
    documents_unchanged: tuple[str, ...]
    new_routes: tuple[str, ...]
    removed_routes: tuple[str, ...]
    new_models: tuple[str, ...]
    removed_models: tuple[str, ...]
    #: ``Project`` field names whose value differs from the previous cache
    #: (or every field, on a first run / invalidated cache — there is no
    #: baseline to compare against).
    changed_categories: tuple[str, ...]
    duration_seconds: float
    #: True when nothing could be reused — a first run, a forced run, or
    #: an invalid cache all fall back to a full pass (D-045, D-047).
    forced_full_analysis: bool
