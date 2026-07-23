"""DATABASE.md: detected SQLAlchemy, Pydantic and Django ORM models."""

from __future__ import annotations

from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Detected database/schema models: ORM, table name and fields."


def render(project: Project) -> Document:
    parts = [markdown.heading("Database Models", 1)]

    if project.database_models:
        rows = [
            [
                model.name,
                model.orm,
                model.table_name or "-",
                markdown.code(str(model.file)),
                ", ".join(model.fields) or "-",
            ]
            for model in project.database_models
        ]
        parts.append(markdown.table(["Model", "ORM", "Table", "File", "Fields"], rows))
    else:
        parts.append(markdown.paragraph("No database models detected."))

    body = "\n".join(parts)
    return Document("DATABASE.md", "Database Models", _DESCRIPTION, body)
