"""Save your Tokens — deterministic repository analysis engine.

This package is the reusable core of the project. It has no dependency on
MCP, on any CLI framework, or on any language model. Every interface (CLI,
MCP server, future web API) is built *on top of* this package, never the
other way around.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from analyzer.detectors import identify_project
from analyzer.models import (
    Confidence,
    Detection,
    FileInfo,
    LanguageStat,
    Project,
    RepositoryStats,
)
from analyzer.scanner import scan_repository

__version__ = "0.2.0"

__all__ = [
    "Confidence",
    "Detection",
    "FileInfo",
    "LanguageStat",
    "Project",
    "RepositoryStats",
    "analyze_repository",
    "identify_project",
    "scan_repository",
    "__version__",
]


def analyze_repository(
    root: Path | str,
    *,
    extra_ignored_directories: Iterable[str] = (),
    include_hidden: bool = False,
    follow_symlinks: bool = False,
) -> Project:
    """Scan and identify a repository in one call.

    Equivalent to ``identify_project(scan_repository(root, ...))`` — the
    composition most callers (CLI, future MCP tools) actually want. Kept as
    two separately testable functions rather than merged, since "walk the
    tree" and "identify what's in it" are different concerns.
    """
    project = scan_repository(
        root,
        extra_ignored_directories=extra_ignored_directories,
        include_hidden=include_hidden,
        follow_symlinks=follow_symlinks,
    )
    return identify_project(project)
