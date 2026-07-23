"""API_ROUTES.md: detected FastAPI/Flask/Django routes."""

from __future__ import annotations

from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Detected HTTP routes: method, path, handler and framework."


def render(project: Project) -> Document:
    parts = [markdown.heading("API Routes", 1)]

    if project.routes:
        rows = [
            [
                route.method,
                markdown.code(route.path),
                markdown.code(route.handler),
                markdown.code(str(route.file)),
                route.framework,
            ]
            for route in project.routes
        ]
        parts.append(
            markdown.table(["Method", "Path", "Handler", "File", "Framework"], rows)
        )
    else:
        parts.append(markdown.paragraph("No API routes detected."))

    body = "\n".join(parts)
    return Document("API_ROUTES.md", "API Routes", _DESCRIPTION, body)
