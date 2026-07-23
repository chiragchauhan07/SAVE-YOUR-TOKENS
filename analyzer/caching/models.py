"""Data shapes for the incremental caching layer.

These are the caching layer's own types — repository change facts and the
persisted cache shape — not general analysis facts, so they live here
rather than in ``analyzer.models`` (same reasoning as every other layer's
own ``models.py`` in this project: detected/produced facts stay separate
from each layer's presentation or bookkeeping types).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from analyzer.models import (
    DatabaseModel,
    Detection,
    EntryPoint,
    ImportantFile,
    ImportEdge,
    ModuleDependency,
    ModuleInfo,
    Route,
)

#: Bump whenever the cache file's shape changes incompatibly. A mismatch
#: means "don't trust this cache", never "guess how to migrate it" (D-045).
CACHE_SCHEMA_VERSION = 1


class CacheStatus(StrEnum):
    """Why the cache was or wasn't used this run."""

    MISSING = "missing"
    VALID = "valid"
    CORRUPTED = "corrupted"
    VERSION_MISMATCH = "version_mismatch"
    TOOL_VERSION_MISMATCH = "tool_version_mismatch"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    """What the cache remembers about one file, to detect change cheaply.

    ``content_hash`` (``"sha256:<hex>"``) is always populated — the
    size/mtime pair is only ever used as a fast pre-check to *avoid*
    re-hashing an unchanged file (D-045), never as a substitute for the
    hash itself.
    """

    size: int
    mtime: float
    content_hash: str


@dataclass(frozen=True, slots=True)
class RenamedFile:
    """A deleted path and a new path detected as the same content (D-046)."""

    old_path: PurePosixPath
    new_path: PurePosixPath


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """What changed in the repository since the cached snapshot."""

    new_files: tuple[PurePosixPath, ...]
    modified_files: tuple[PurePosixPath, ...]
    deleted_files: tuple[PurePosixPath, ...]
    renamed_files: tuple[RenamedFile, ...]
    unchanged_count: int

    @property
    def has_changes(self) -> bool:
        return bool(
            self.new_files
            or self.modified_files
            or self.deleted_files
            or self.renamed_files
        )

    @property
    def files_to_reparse(self) -> frozenset[str]:
        """New or modified ``.py`` files — the only ones needing a fresh AST parse."""
        return frozenset(
            str(path)
            for path in (*self.new_files, *self.modified_files)
            if path.suffix == ".py"
        )


@dataclass(frozen=True, slots=True)
class Cache:
    """The full persisted cache: file fingerprints plus the last known
    per-file-safe analysis results (D-044) and the last known values of
    everything else, kept only for change reporting (D-047).
    """

    cache_version: int
    tool_version: str
    repository_root: str
    fingerprints: dict[str, FileFingerprint]
    entry_points: tuple[EntryPoint, ...]
    modules: tuple[ModuleInfo, ...]
    routes: tuple[Route, ...]
    database_models: tuple[DatabaseModel, ...]
    imports: tuple[ImportEdge, ...]
    circular_imports: tuple[tuple[str, ...], ...]
    module_dependencies: tuple[ModuleDependency, ...]
    authentication: tuple[Detection, ...]
    configuration: tuple[Detection, ...]
    important_files: tuple[ImportantFile, ...]
