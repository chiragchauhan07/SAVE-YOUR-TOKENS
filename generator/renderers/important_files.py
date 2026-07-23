"""IMPORTANT_FILES.md: the full evidence-ranked file list.

ARCHITECTURE.md shows only the top ten with a pointer here; this file is
the complete ranking.
"""

from __future__ import annotations

from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Every ranked file, its score, and why it was ranked."


def render(project: Project) -> Document:
    parts = [markdown.heading("Important Files", 1)]

    if project.important_files:
        rows = [
            [markdown.code(str(f.file)), str(f.score), "; ".join(f.reasons)]
            for f in project.important_files
        ]
        parts.append(markdown.table(["File", "Score", "Reasons"], rows))
    else:
        parts.append(markdown.paragraph("No files received a ranking signal."))

    body = "\n".join(parts)
    return Document("IMPORTANT_FILES.md", "Important Files", _DESCRIPTION, body)
