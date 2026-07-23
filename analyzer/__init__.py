"""Save your Tokens — deterministic repository analysis engine.

This package is the reusable core of the project. It has no dependency on
MCP, on any CLI framework, or on any language model. Every interface (CLI,
MCP server, future web API) is built *on top of* this package, never the
other way around.
"""

from analyzer.models import FileInfo, Project, RepositoryStats
from analyzer.scanner import scan_repository

__version__ = "0.1.0"

__all__ = [
    "FileInfo",
    "Project",
    "RepositoryStats",
    "scan_repository",
    "__version__",
]
