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
class EntryPoint:
    """A point where the application starts running.

    ``kind`` is one of ``"script"`` (an ``if __name__ == "__main__":``
    guard), ``"fastapi_app"``, ``"flask_app"`` or ``"django_manage"``.
    ``symbol`` is the app variable name for ``fastapi_app``/``flask_app``
    (e.g. ``"app"``), ``None`` otherwise.
    """

    file: PurePosixPath
    kind: str
    symbol: str | None
    confidence: Confidence
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ImportEdge:
    """One import statement, and whether it resolves inside this repository.

    ``module`` is the import as written: a dotted absolute name, or a
    dot-prefixed relative form (``".foo"``, ``".."``) mirroring the source.
    """

    file: PurePosixPath
    module: str
    is_internal: bool
    #: The internal file this import resolves to, when ``is_internal``.
    resolved_file: PurePosixPath | None


@dataclass(frozen=True, slots=True)
class ModuleInfo:
    """Structural metadata for one Python module — never business logic."""

    file: PurePosixPath
    classes: tuple[str, ...]
    functions: tuple[str, ...]
    async_functions: tuple[str, ...]
    #: Module-level UPPER_CASE assignments — the recognised constant convention.
    constants: tuple[str, ...]
    #: ``__all__`` if declared, else every non-underscore-prefixed top-level name.
    exports: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Route:
    """One detected HTTP route. Detection only — never what the handler does."""

    method: str
    path: str
    handler: str
    file: PurePosixPath
    #: "FastAPI", "Flask" or "Django".
    framework: str


@dataclass(frozen=True, slots=True)
class DatabaseModel:
    """One detected ORM/schema model. Structure only — no semantic interpretation."""

    name: str
    #: "SQLAlchemy", "Pydantic" or "Django ORM".
    orm: str
    #: Explicit ``__tablename__``, when declared.
    table_name: str | None
    file: PurePosixPath
    fields: tuple[str, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModuleDependency:
    """A directed internal-import edge between two files in this repository."""

    source: PurePosixPath
    target: PurePosixPath


@dataclass(frozen=True, slots=True)
class ImportantFile:
    """A file ranked by evidence-based signals — never a hardcoded name."""

    file: PurePosixPath
    score: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Project:
    """The complete result of scanning, identifying and analysing a repository.

    This is the object every later phase (context generation) consumes as
    its input. ``files`` and ``stats`` come from the Phase 1 scanner;
    ``languages`` through ``repository_type`` from the Phase 2 identification
    detectors (``analyzer.detectors``); ``entry_points`` through
    ``important_files`` from the Phase 3 intelligence layer
    (``analyzer.intelligence``). Every field beyond ``files``/``stats``
    defaults to empty until the corresponding phase has run.
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
    entry_points: tuple[EntryPoint, ...] = ()
    modules: tuple[ModuleInfo, ...] = ()
    imports: tuple[ImportEdge, ...] = ()
    #: Each cycle is a sequence of internal file paths (as strings) forming
    #: an import loop, e.g. ``("app/auth.py", "app/database.py")``.
    circular_imports: tuple[tuple[str, ...], ...] = ()
    routes: tuple[Route, ...] = ()
    database_models: tuple[DatabaseModel, ...] = ()
    authentication: tuple[Detection, ...] = ()
    configuration: tuple[Detection, ...] = ()
    module_dependencies: tuple[ModuleDependency, ...] = ()
    important_files: tuple[ImportantFile, ...] = ()

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
