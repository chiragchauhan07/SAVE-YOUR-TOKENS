"""Shared Python AST parsing helpers for the Phase 3 intelligence layer.

Every intelligence module works from ``ast.Module`` trees produced here —
never re-parses a file, never executes analyzed code (no import, no eval, no
exec of anything in the target repository; see D-018). A file that fails to
parse — a real syntax error, or syntax newer than this tool's own Python
runtime can read — is silently skipped: one broken file must never abort
analysis of the rest.

Python-only for now. A second language means a new sibling package
following the same shape (one function per concern, ``Project`` in, typed
results out) — nothing here is Python-specific by name, only by
implementation, so this module itself doesn't need to change.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from analyzer.models import FileInfo, Project

#: Defensive cap, not a real limit — guards against pathological generated
#: files (e.g. a multi-hundred-MB generated protobuf module).
_MAX_SOURCE_BYTES = 2_000_000


@dataclass(frozen=True, slots=True)
class ParsedModule:
    """A Python file that parsed successfully, with its AST."""

    file: FileInfo
    tree: ast.Module


def parse_python_files(project: Project) -> tuple[ParsedModule, ...]:
    """Parse every Python file in the project, skipping ones that fail."""
    parsed = []
    for file in project.files_with_extension(".py"):
        tree = _parse_file(project, file)
        if tree is not None:
            parsed.append(ParsedModule(file, tree))
    return tuple(parsed)


def _parse_file(project: Project, file: FileInfo) -> ast.Module | None:
    if file.size_bytes > _MAX_SOURCE_BYTES:
        return None
    path = project.root / str(file.path)
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        return ast.parse(source, filename=str(file.path))
    except (OSError, SyntaxError, ValueError, RecursionError):
        return None


def simple_name(expr: ast.expr) -> str | None:
    """The rightmost name in a ``Name`` or ``Attribute`` expression.

    ``"FastAPI"`` from both ``FastAPI`` and ``fastapi.FastAPI``. ``None`` for
    any other expression shape (a subscript, a call result, ...).
    """
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def qualifier_name(expr: ast.expr) -> str | None:
    """The left-hand name of a two-part dotted attribute.

    ``"db"`` from ``db.Model``; ``None`` for a bare name or anything deeper.
    """
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        return expr.value.id
    return None
