"""Core domain models produced by the analysis engine.

These types are the contract between the Analysis Engine and every consumer
(CLI, MCP server, future web/API layers). They are deliberately free of any
MCP, transport or presentation concern.

All models are frozen: a scan result is a snapshot, not a mutable buffer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path, PurePosixPath

from analyzer.constants import LARGEST_FILES_COUNT


@dataclass(frozen=True, slots=True)
class FileInfo:
    """A single source file that survived the ignore rules."""

    #: Path relative to the repository root, always POSIX-style so that scan
    #: output is identical on Windows and Unix.
    path: PurePosixPath
    size_bytes: int
    #: Lowercased extension including the leading dot, or "" when the file
    #: has none (``Makefile``, ``Dockerfile``, ``.gitignore``).
    extension: str

    @property
    def name(self) -> str:
        """The file name without its directory."""
        return self.path.name

    @property
    def depth(self) -> int:
        """Directory nesting level; a file at the repository root is 0."""
        return len(self.path.parts) - 1


@dataclass(frozen=True, slots=True)
class RepositoryStats:
    """Aggregate counts derived from the scanned files."""

    total_files: int
    total_directories: int
    total_size_bytes: int
    #: Extension -> file count, ordered most frequent first. Files without an
    #: extension are grouped under the empty string.
    files_by_extension: dict[str, int]
    largest_files: tuple[FileInfo, ...]

    @classmethod
    def from_files(
        cls,
        files: tuple[FileInfo, ...],
        total_directories: int,
    ) -> RepositoryStats:
        """Derive statistics from an already-scanned, sorted file list."""
        counts = Counter(file.extension for file in files)
        # Ties broken by extension name so the output stays deterministic.
        by_extension = dict(
            sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        )
        largest = tuple(
            sorted(files, key=lambda f: (-f.size_bytes, str(f.path)))[
                :LARGEST_FILES_COUNT
            ]
        )
        return cls(
            total_files=len(files),
            total_directories=total_directories,
            total_size_bytes=sum(file.size_bytes for file in files),
            files_by_extension=by_extension,
            largest_files=largest,
        )


class Confidence(IntEnum):
    """How strong a detector's evidence is. Ordered: HIGH > MEDIUM > LOW.

    HIGH means unambiguous evidence (a dependency named in a manifest, a
    lockfile). MEDIUM means a conventional signal without manifest
    confirmation (``manage.py`` present but Django absent from every
    manifest we read). Detectors never report a match with no evidence at
    all — "unknown" is a valid result, a guess is not.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3


@dataclass(frozen=True, slots=True)
class Detection:
    """A single identified technology, tool or repository trait.

    Used for frameworks, package managers, build tools, CI providers,
    container tooling, environment surfaces and the overall repository
    classification — anywhere a detector reports "I found X, here's why".
    """

    name: str
    confidence: Confidence
    #: Human-readable evidence lines, e.g. ``"dependency: fastapi"`` or
    #: ``"file: manage.py"``. Never empty — a Detection is only created once
    #: there is something to point at.
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LanguageStat:
    """Prevalence of one programming/markup language in the repository."""

    name: str
    file_count: int
    size_bytes: int
    #: Share of total recognised-language bytes, 0-100, one decimal place.
    percentage: float


@dataclass(frozen=True, slots=True)
class Project:
    """The complete result of scanning and identifying a repository.

    This is the object every later phase (deep analysis, context
    generation) consumes as its input. ``files`` and ``stats`` are produced
    by the Phase 1 scanner; every field below them is produced by the
    Phase 2 identification detectors (``analyzer.detectors``) and defaults
    to empty until ``identify_project()`` has run.
    """

    #: Absolute, resolved path to the repository root.
    root: Path
    #: Directory name of the repository root.
    name: str
    #: Every retained file, sorted by path for deterministic output.
    files: tuple[FileInfo, ...] = field(repr=False)
    stats: RepositoryStats
    languages: tuple[LanguageStat, ...] = ()
    frameworks: tuple[Detection, ...] = ()
    package_managers: tuple[Detection, ...] = ()
    build_tools: tuple[Detection, ...] = ()
    ci_providers: tuple[Detection, ...] = ()
    container_tools: tuple[Detection, ...] = ()
    environment_files: tuple[Detection, ...] = ()
    #: Overall classification (e.g. "Full Stack Web Application"), or
    #: ``None`` before identification has run. Never a guess: an
    #: unidentifiable repository gets an explicit "Unknown" Detection, not
    #: ``None`` after ``identify_project()`` has run.
    repository_type: Detection | None = None

    def files_with_extension(self, extension: str) -> tuple[FileInfo, ...]:
        """All files matching ``extension`` (e.g. ``".py"``)."""
        wanted = extension.lower()
        return tuple(file for file in self.files if file.extension == wanted)

    def find(self, name: str) -> tuple[FileInfo, ...]:
        """All files whose file name equals ``name``, case-insensitively.

        Used by later phases to locate manifests such as ``package.json``
        or ``pyproject.toml``.
        """
        wanted = name.lower()
        return tuple(file for file in self.files if file.name.lower() == wanted)
