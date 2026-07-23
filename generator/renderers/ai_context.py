"""AI_CONTEXT.md: the primary entry point for an AI coding assistant.

Unlike every other renderer, this one also needs the full document list —
it builds a recommended reading order over the *other* generated files
rather than presenting `Project` data directly.
"""

from __future__ import annotations

from collections import Counter

from analyzer.constants import IGNORED_DIRECTORIES
from analyzer.models import Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = (
    "Start here. Orientation for an AI assistant before it reads source files."
)
_TOP_CRITICAL_FILES = 10


def render(project: Project, documents: tuple[Document, ...]) -> Document:
    parts = [markdown.heading("AI Context", 1)]
    parts.append(
        markdown.paragraph(
            "Read this file first. It orients an AI coding assistant before "
            "it opens any repository source file."
        )
    )

    parts.append(markdown.heading("At a Glance", 2))
    parts.append(markdown.table(["Metric", "Value"], _at_a_glance_rows(project)))

    descriptions = {document.filename: document.description for document in documents}
    parts.append(markdown.heading("Recommended Reading Order", 2))
    parts.append(
        markdown.bullet_list(
            [
                f"[{filename}]({filename}) — {descriptions[filename]}"
                for filename in _reading_order(project)
            ]
        )
    )

    parts.append(markdown.heading("Entry Points", 2))
    if project.entry_points:
        parts.append(
            markdown.bullet_list(
                [
                    f"{markdown.code(str(ep.file))} ({ep.kind})"
                    for ep in project.entry_points
                ]
            )
        )
    else:
        parts.append(markdown.paragraph("None detected."))

    parts.append(markdown.heading("Critical Files", 2))
    top_files = project.important_files[:_TOP_CRITICAL_FILES]
    if top_files:
        parts.append(
            markdown.bullet_list([markdown.code(str(f.file)) for f in top_files])
        )
    else:
        parts.append(markdown.paragraph("No file received a ranking signal."))

    parts.append(markdown.heading("Important Directories", 2))
    directories = _important_directories(project)
    if directories:
        parts.append(markdown.bullet_list([markdown.code(d) for d in directories]))
    else:
        parts.append(
            markdown.paragraph("No directory concentrated enough signal to highlight.")
        )

    parts.append(markdown.heading("Excluded From Analysis", 2))
    parts.append(
        markdown.paragraph(
            "The scanner already excludes these directory categories; there is no "
            "need to explore them for repository understanding."
        )
    )
    parts.append(
        markdown.bullet_list([markdown.code(d) for d in sorted(IGNORED_DIRECTORIES)])
    )

    body = "\n".join(parts)
    return Document("AI_CONTEXT.md", "AI Context", _DESCRIPTION, body)


def _at_a_glance_rows(project: Project) -> list[list[str]]:
    return [
        [
            "Repository Type",
            project.repository_type.name if project.repository_type else "Unknown",
        ],
        ["Entry Points", str(len(project.entry_points))],
        ["Modules Analysed", str(len(project.modules))],
        ["API Routes", str(len(project.routes))],
        ["Database Models", str(len(project.database_models))],
        ["Authentication Mechanisms", str(len(project.authentication))],
        ["Configuration Surfaces", str(len(project.configuration))],
        ["Module Dependencies", str(len(project.module_dependencies))],
        ["Circular Imports", str(len(project.circular_imports))],
    ]


def _reading_order(project: Project) -> list[str]:
    order = ["OVERVIEW.md", "ARCHITECTURE.md"]
    if project.routes:
        order.append("API_ROUTES.md")
    if project.database_models:
        order.append("DATABASE.md")
    if project.authentication:
        order.append("AUTHENTICATION.md")
    if project.configuration:
        order.append("CONFIGURATION.md")
    order += ["MODULES.md", "DEPENDENCIES.md"]
    return order


def _important_directories(project: Project) -> list[str]:
    counts: Counter[str] = Counter()
    for important_file in project.important_files:
        directory_parts = important_file.file.parts[:-1]
        if directory_parts:
            counts[directory_parts[0]] += 1
    return [
        name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
