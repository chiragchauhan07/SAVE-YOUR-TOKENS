"""Exception classification: turn a real exception into a safe ``ToolError``.

The only place this project decides what's safe to tell an MCP client.
``tools.py`` calls ``classify_exception`` for every exception it catches and
returns the result — never the exception's own message for anything beyond
the two cases below, whose messages are already deliberately-authored safe
text (see ``analyzer.utils.validate_repository_path``), and never a
traceback under any circumstance.
"""

from __future__ import annotations

from typing import Literal

from mcp_server.models import ErrorType, ToolError

Phase = Literal["analysis", "generation", "cache", "health"]


def classify_exception(exc: Exception, *, phase: Phase) -> ToolError:
    """Map a caught exception to a typed, safe-to-return ``ToolError``."""
    if isinstance(exc, FileNotFoundError):
        # analyzer.utils.validate_repository_path already builds a clean,
        # deliberate message ("Repository path does not exist: <path>") —
        # safe to pass through verbatim.
        return ToolError(ErrorType.NOT_FOUND, str(exc))

    if isinstance(exc, NotADirectoryError):
        return ToolError(ErrorType.INVALID_REPOSITORY, str(exc))

    if isinstance(exc, PermissionError):
        action = (
            "writing the Knowledge Base or cache"
            if phase in ("generation", "cache")
            else "reading the repository"
        )
        return ToolError(
            ErrorType.PERMISSION_DENIED, f"Permission denied while {action}."
        )

    if phase == "generation":
        return ToolError(
            ErrorType.GENERATION_FAILED,
            "Knowledge Base generation failed unexpectedly.",
        )
    if phase == "analysis":
        return ToolError(
            ErrorType.ANALYSIS_FAILED, "Repository analysis failed unexpectedly."
        )
    return ToolError(ErrorType.INTERNAL_ERROR, "An unexpected error occurred.")
