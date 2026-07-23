"""DEPENDENCIES.md: the full import graph — module dependencies, circular
imports, and the most-imported external packages.
"""

from __future__ import annotations

from collections import Counter

from analyzer.models import ImportEdge, Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Module dependency graph, circular imports, and external package usage."


def render(project: Project) -> Document:
    parts = [markdown.heading("Dependencies", 1)]

    parts.append(markdown.heading("Module Dependencies", 2))
    if project.module_dependencies:
        rows = [
            [markdown.code(str(dep.source)), markdown.code(str(dep.target))]
            for dep in project.module_dependencies
        ]
        parts.append(markdown.table(["Source", "Depends On"], rows))
    else:
        parts.append(markdown.paragraph("No internal module dependencies detected."))

    parts.append(markdown.heading("Circular Imports", 2))
    if project.circular_imports:
        rows = [[_format_cycle(cycle)] for cycle in project.circular_imports]
        parts.append(markdown.table(["Cycle"], rows))
    else:
        parts.append(markdown.paragraph("No circular imports detected."))

    parts.append(markdown.heading("External Dependencies", 2))
    external_counts = _count_external_packages(project.imports)
    if external_counts:
        rows = [[markdown.code(name), str(count)] for name, count in external_counts]
        parts.append(markdown.table(["Package", "Import Count"], rows))
    else:
        parts.append(markdown.paragraph("No external imports detected."))

    body = "\n".join(parts)
    return Document("DEPENDENCIES.md", "Dependencies", _DESCRIPTION, body)


def _format_cycle(cycle: tuple[str, ...]) -> str:
    files = [markdown.code(file) for file in cycle]
    return " → ".join([*files, files[0]])


def _count_external_packages(imports: tuple[ImportEdge, ...]) -> list[tuple[str, int]]:
    # An unresolvable relative import (`from .. import x` beyond the
    # top-level package) is also `is_internal=False`, but its module string
    # is dot-prefixed with no real package name — excluded here, since it
    # isn't an external package, just an import we couldn't resolve.
    counts: Counter[str] = Counter(
        edge.module.split(".")[0]
        for edge in imports
        if not edge.is_internal and not edge.module.startswith(".")
    )
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))
