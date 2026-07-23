"""Internal module dependency relationships, derived from the import graph.

The hard work (parsing, resolving imports) already happened in
``imports.py``; this module's whole job is reshaping internal-only edges
into a deduplicated, self-loop-free dependency list.
"""

from __future__ import annotations

from analyzer.models import ImportEdge, ModuleDependency


def build_module_dependencies(
    imports: tuple[ImportEdge, ...],
) -> tuple[ModuleDependency, ...]:
    seen: set[tuple[str, str]] = set()
    dependencies = []
    for edge in imports:
        if not edge.is_internal or edge.resolved_file is None:
            continue
        if edge.file == edge.resolved_file:
            continue
        key = (str(edge.file), str(edge.resolved_file))
        if key in seen:
            continue
        seen.add(key)
        dependencies.append(ModuleDependency(edge.file, edge.resolved_file))
    return tuple(
        sorted(
            dependencies,
            key=lambda dependency: (str(dependency.source), str(dependency.target)),
        )
    )
