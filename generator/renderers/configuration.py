"""CONFIGURATION.md: detected settings modules, config classes, environment
loading and dotenv usage. Environment *file* conventions (``.env.example``)
are Phase 2 data and stay in OVERVIEW.md — cross-referenced from here
rather than duplicated.
"""

from __future__ import annotations

from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Settings modules, config classes, and environment/dotenv usage."


def render(project: Project) -> Document:
    parts = [markdown.heading("Configuration", 1)]

    table = markdown.detection_table(project.configuration)
    if table:
        parts.append(table)
    else:
        parts.append(markdown.paragraph("No configuration surfaces detected."))

    parts.append(
        markdown.paragraph(
            "Environment file conventions (e.g. `.env.example`) are listed "
            "in OVERVIEW.md."
        )
    )

    body = "\n".join(parts)
    return Document("CONFIGURATION.md", "Configuration", _DESCRIPTION, body)
