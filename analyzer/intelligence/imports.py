"""Import graph construction: internal vs. external imports, and circular
import detection among internal modules.

Absolute imports (``import a.b``, ``from a.b import c``) resolve against the
repository root only — a deliberate simplification for ``src``-layout
projects; see D-019. Relative imports (``from . import x``, ``from ..a import
b``) resolve against the importing file's own package directory, following
the same level-counting rule CPython uses (``importlib._bootstrap._resolve_name``).

``from package import name`` resolution is two-tier: ``name`` might be a
submodule of ``package`` (``from analyzer.detectors import manifests`` ->
``analyzer/detectors/manifests.py``) or a name defined inside the package's
own ``__init__.py`` (``from analyzer.detectors import identify_project`` ->
``analyzer/detectors/__init__.py``). Resolving every such import to the
package's ``__init__.py`` regardless would fabricate cycles that don't exist
at runtime — see D-021.
"""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

from analyzer.intelligence.common import parse_python_files
from analyzer.models import ImportEdge, Project


def analyze_imports(project: Project) -> tuple[ImportEdge, ...]:
    """Every import statement in the repository, resolved where possible."""
    parsed_modules = parse_python_files(project)
    existing_paths = frozenset(str(file.path) for file in project.files)
    edges: list[ImportEdge] = []

    for parsed in parsed_modules:
        for node in ast.walk(parsed.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    resolved = _find_module_file(existing_paths, alias.name.split("."))
                    edges.append(
                        ImportEdge(
                            parsed.file.path, alias.name, resolved is not None, resolved
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                base_parts = _resolve_base_parts(
                    parsed.file.path, node.module, node.level
                )
                for alias in node.names:
                    resolved = (
                        _resolve_from_name(existing_paths, base_parts, alias.name)
                        if base_parts is not None
                        else None
                    )
                    module_repr = _format_from_import(
                        node.module, node.level, alias.name
                    )
                    edges.append(
                        ImportEdge(
                            parsed.file.path,
                            module_repr,
                            resolved is not None,
                            resolved,
                        )
                    )

    return tuple(sorted(edges, key=lambda edge: (str(edge.file), edge.module)))


def detect_circular_imports(
    imports: tuple[ImportEdge, ...],
) -> tuple[tuple[str, ...], ...]:
    """Cycles among internal-only import edges, found by DFS.

    One representative cycle per back-edge encountered, not an exhaustive
    enumeration of every cycle — exhaustive cycle enumeration is
    combinatorially expensive and not what a repository summary needs.
    """
    graph: dict[str, set[str]] = {}
    for edge in imports:
        if (
            edge.is_internal
            and edge.resolved_file is not None
            and str(edge.file) != str(edge.resolved_file)
        ):
            graph.setdefault(str(edge.file), set()).add(str(edge.resolved_file))

    cycles: list[tuple[str, ...]] = []
    visited: set[str] = set()

    def visit(node: str, stack: list[str], on_stack: set[str]) -> None:
        visited.add(node)
        stack.append(node)
        on_stack.add(node)
        for neighbor in sorted(graph.get(node, ())):
            if neighbor in on_stack:
                cycle_start = stack.index(neighbor)
                cycles.append(_normalize_cycle(tuple(stack[cycle_start:])))
            elif neighbor not in visited:
                visit(neighbor, stack, on_stack)
        stack.pop()
        on_stack.discard(node)

    for node in sorted(graph):
        if node not in visited:
            visit(node, [], set())

    return tuple(sorted(set(cycles)))


def _normalize_cycle(cycle: tuple[str, ...]) -> tuple[str, ...]:
    """Rotate a cycle to start at its lexicographically smallest node.

    Makes ``A -> B -> A`` and ``B -> A -> B`` compare equal, so the same
    cycle found from two different starting points is reported once.
    """
    start = cycle.index(min(cycle))
    return cycle[start:] + cycle[:start]


def _resolve_base_parts(
    importing_file: PurePosixPath, module: str | None, level: int
) -> tuple[str, ...] | None:
    """The dotted path components of the ``from X import ...`` target ``X``."""
    if level > 0:
        relative_base = _relative_base_parts(importing_file, level)
        if relative_base is None:
            return None
        return relative_base + tuple(module.split(".")) if module else relative_base

    if not module:
        return None
    return tuple(module.split("."))


def _relative_base_parts(
    importing_file: PurePosixPath, level: int
) -> tuple[str, ...] | None:
    """The directory ``level`` dots resolve to, or ``None`` if that goes
    above the top-level package (mirrors CPython's own bounds check).
    """
    directory_parts = importing_file.parts[:-1]
    ups = level - 1
    if ups >= len(directory_parts):
        return None
    return directory_parts[: len(directory_parts) - ups]


def _resolve_from_name(
    existing_paths: frozenset[str], base_parts: tuple[str, ...], name: str
) -> PurePosixPath | None:
    """Resolve one name from ``from <base_parts> import name``.

    Tries ``name`` as a submodule of the base package first, then falls
    back to the base module/package itself (``name`` is an attribute
    defined there, not a file of its own).
    """
    submodule = _find_module_file(existing_paths, [*base_parts, name])
    if submodule is not None:
        return submodule
    return _find_module_file(existing_paths, list(base_parts))


def _find_module_file(
    existing_paths: frozenset[str], parts: list[str]
) -> PurePosixPath | None:
    if not parts:
        return None
    base = PurePosixPath(*parts)
    candidate_file = base.with_suffix(".py")
    if str(candidate_file) in existing_paths:
        return candidate_file
    candidate_package = base / "__init__.py"
    if str(candidate_package) in existing_paths:
        return candidate_package
    return None


def _format_from_import(module: str | None, level: int, name: str) -> str:
    prefix = "." * level + (module or "")
    if level and not module:
        return prefix + name
    return prefix + "." + name
