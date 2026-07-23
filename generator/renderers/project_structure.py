"""PROJECT_STRUCTURE.md: file/directory statistics from the Phase 1 scan."""

from __future__ import annotations

from analyzer.models import Project
from analyzer.utils import human_readable_size
from generator import markdown
from generator.models import Document

_DESCRIPTION = "File and directory statistics: counts, size, largest files."


def render(project: Project) -> Document:
    stats = project.stats
    parts = [markdown.heading("Project Structure", 1)]

    summary_rows = [
        ["Total files", f"{stats.total_files:,}"],
        ["Total directories", f"{stats.total_directories:,}"],
        ["Total size", human_readable_size(stats.total_size_bytes)],
    ]
    parts.append(markdown.table(["Metric", "Value"], summary_rows))

    parts.append(markdown.heading("File Types", 2))
    if stats.files_by_extension:
        rows = [
            [extension or "(no extension)", f"{count:,}"]
            for extension, count in stats.files_by_extension.items()
        ]
        parts.append(markdown.table(["Extension", "Count"], rows))
    else:
        parts.append(markdown.paragraph("No files found."))

    parts.append(markdown.heading("Largest Files", 2))
    if stats.largest_files:
        rows = [
            [markdown.code(str(file.path)), human_readable_size(file.size_bytes)]
            for file in stats.largest_files
        ]
        parts.append(markdown.table(["File", "Size"], rows))
    else:
        parts.append(markdown.paragraph("No files found."))

    body = "\n".join(parts)
    return Document("PROJECT_STRUCTURE.md", "Project Structure", _DESCRIPTION, body)
