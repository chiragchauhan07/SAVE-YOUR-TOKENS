"""ARCHITECTURE.md: entry points, top important files, and a dependency
summary — the structural skeleton. Full detail lives in IMPORTANT_FILES.md
and DEPENDENCIES.md; this file is the synthesis that links to both.
"""

from __future__ import annotations

from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Entry points, most important files, and a dependency graph summary."
_TOP_IMPORTANT_FILES = 10


def render(project: Project) -> Document:
    parts = [markdown.heading("Architecture", 1)]

    parts.append(markdown.heading("Entry Points", 2))
    if project.entry_points:
        rows = [
            [markdown.code(str(ep.file)), ep.kind, ep.symbol or "-", ep.confidence.name]
            for ep in project.entry_points
        ]
        parts.append(markdown.table(["File", "Kind", "Symbol", "Confidence"], rows))
    else:
        parts.append(markdown.paragraph("No entry points detected."))

    parts.append(markdown.heading("Most Important Files", 2))
    top_files = project.important_files[:_TOP_IMPORTANT_FILES]
    if top_files:
        rows = [
            [markdown.code(str(f.file)), str(f.score), "; ".join(f.reasons)]
            for f in top_files
        ]
        parts.append(markdown.table(["File", "Score", "Reasons"], rows))
        if len(project.important_files) > _TOP_IMPORTANT_FILES:
            parts.append(
                markdown.paragraph("See IMPORTANT_FILES.md for the full ranking.")
            )
    else:
        parts.append(markdown.paragraph("No files received a ranking signal."))

    parts.append(markdown.heading("Dependency Summary", 2))
    internal_count = sum(1 for edge in project.imports if edge.is_internal)
    summary_rows = [
        ["Total imports", str(len(project.imports))],
        ["Internal imports", str(internal_count)],
        ["External imports", str(len(project.imports) - internal_count)],
        ["Module dependency edges", str(len(project.module_dependencies))],
        ["Circular import cycles", str(len(project.circular_imports))],
    ]
    parts.append(markdown.table(["Metric", "Value"], summary_rows))
    parts.append(markdown.paragraph("See DEPENDENCIES.md for the full import graph."))

    body = "\n".join(parts)
    return Document("ARCHITECTURE.md", "Architecture", _DESCRIPTION, body)
