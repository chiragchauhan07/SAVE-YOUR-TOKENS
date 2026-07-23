"""Repository scanner: the entry point of the analysis engine.

Phase 1 scope. The scanner walks a repository, applies deterministic ignore
rules and returns a :class:`~analyzer.models.Project`. It deliberately does
**not** open or parse any file — content analysis belongs to later phases.

Determinism is a hard requirement: two scans of an unchanged repository must
produce byte-identical output, so directories and files are always visited in
sorted order.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from analyzer.constants import (
    IGNORED_DIRECTORIES,
    IGNORED_FILE_EXTENSIONS,
    IGNORED_FILE_NAMES,
)
from analyzer.models import FileInfo, Project, RepositoryStats
from analyzer.utils import extension_of, is_hidden, validate_repository_path


def scan_repository(
    root: Path | str,
    *,
    extra_ignored_directories: Iterable[str] = (),
    include_hidden: bool = False,
    follow_symlinks: bool = False,
) -> Project:
    """Scan ``root`` and return a structured :class:`Project`.

    Args:
        root: Path to the repository to analyse.
        extra_ignored_directories: Additional directory names to prune, on
            top of :data:`~analyzer.constants.IGNORED_DIRECTORIES`.
        include_hidden: Retain dot-prefixed files and directories. Explicitly
            ignored names (``.git``, ``.venv``, ...) stay ignored regardless.
        follow_symlinks: Descend into symlinked directories. Off by default
            because symlink cycles make a walk non-terminating.

    Raises:
        FileNotFoundError: ``root`` does not exist.
        NotADirectoryError: ``root`` is not a directory.
    """
    repository_root = validate_repository_path(root)
    ignored_directories = IGNORED_DIRECTORIES | set(extra_ignored_directories)

    files: list[FileInfo] = []
    directory_count = 0

    for current_dir, subdirectories, file_names in os.walk(
        repository_root, followlinks=follow_symlinks
    ):
        # In-place assignment is what prunes the walk: os.walk only descends
        # into the directories left in this list, so ignored trees are never
        # entered at all.
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if not _is_ignored_directory(name, ignored_directories, include_hidden)
        )
        directory_count += len(subdirectories)

        current_path = Path(current_dir)
        for file_name in sorted(file_names):
            if _is_ignored_file(file_name, include_hidden):
                continue

            file_info = _describe_file(current_path / file_name, repository_root)
            if file_info is not None:
                files.append(file_info)

    # The walk is already deterministic; sorting makes the ordering a
    # documented property of Project.files rather than a traversal artefact.
    scanned_files = tuple(sorted(files, key=lambda file: str(file.path)))
    return Project(
        root=repository_root,
        name=repository_root.name,
        files=scanned_files,
        stats=RepositoryStats.from_files(scanned_files, directory_count),
    )


def _is_ignored_directory(
    name: str,
    ignored_directories: set[str],
    include_hidden: bool,
) -> bool:
    """Whether a directory should be pruned from the walk."""
    if name in ignored_directories:
        return True
    if not include_hidden and is_hidden(name):
        return True
    # Python packaging leaves these next to the source tree.
    return name.endswith(".egg-info")


def _is_ignored_file(name: str, include_hidden: bool) -> bool:
    """Whether a file should be excluded from the result."""
    if name in IGNORED_FILE_NAMES:
        return True
    if not include_hidden and is_hidden(name):
        return True
    return extension_of(name) in IGNORED_FILE_EXTENSIONS


def _describe_file(absolute_path: Path, repository_root: Path) -> FileInfo | None:
    """Build a :class:`FileInfo`, or ``None`` if the file cannot be read.

    Broken symlinks and permission-denied entries are common in real
    repositories and must not abort an otherwise successful scan.
    """
    try:
        size_bytes = absolute_path.stat().st_size
    except OSError:
        return None

    relative_path = absolute_path.relative_to(repository_root)
    return FileInfo(
        path=PurePosixPath(relative_path.as_posix()),
        size_bytes=size_bytes,
        extension=extension_of(absolute_path.name),
    )
