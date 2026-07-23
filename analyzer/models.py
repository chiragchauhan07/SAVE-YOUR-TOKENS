"""Core domain models produced by the analysis engine.

These types are the contract between the Analysis Engine and every consumer
(CLI, MCP server, future web/API layers). They are deliberately free of any
MCP, transport or presentation concern.

All models are frozen: a scan result is a snapshot, not a mutable buffer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class Project:
    """The complete result of scanning a repository.

    This is the object every later phase (framework detection, route
    discovery, context generation) consumes as its input.
    """

    #: Absolute, resolved path to the repository root.
    root: Path
    #: Directory name of the repository root.
    name: str
    #: Every retained file, sorted by path for deterministic output.
    files: tuple[FileInfo, ...] = field(repr=False)
    stats: RepositoryStats

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
