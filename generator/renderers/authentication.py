"""AUTHENTICATION.md: detected authentication mechanisms."""

from __future__ import annotations

from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Detected authentication mechanisms and their evidence."


def render(project: Project) -> Document:
    parts = [markdown.heading("Authentication", 1)]

    table = markdown.detection_table(project.authentication)
    if table:
        parts.append(table)
    else:
        parts.append(markdown.paragraph("No authentication mechanisms detected."))

    body = "\n".join(parts)
    return Document("AUTHENTICATION.md", "Authentication", _DESCRIPTION, body)
