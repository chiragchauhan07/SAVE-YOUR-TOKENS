"""MODULES.md: per-module classes, functions, constants and exports.

One row per module in a single flat table — not a heading per file. A
table stays compact and scannable even for a large repository; splitting
into per-file sections or paginating is deferred until a real repository
shows the flat table itself becoming the bottleneck (see D-027).
"""

from __future__ import annotations

from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Classes, functions, constants and exports for every analysed module."


def render(project: Project) -> Document:
    parts = [markdown.heading("Modules", 1)]

    if project.modules:
        rows = [
            [
                markdown.code(str(module.file)),
                ", ".join(module.classes) or "-",
                ", ".join(module.functions) or "-",
                ", ".join(module.async_functions) or "-",
                ", ".join(module.constants) or "-",
                ", ".join(module.exports) or "-",
            ]
            for module in project.modules
        ]
        parts.append(
            markdown.table(
                [
                    "File",
                    "Classes",
                    "Functions",
                    "Async Functions",
                    "Constants",
                    "Exports",
                ],
                rows,
            )
        )
    else:
        parts.append(markdown.paragraph("No Python modules analysed."))

    body = "\n".join(parts)
    return Document("MODULES.md", "Modules", _DESCRIPTION, body)
