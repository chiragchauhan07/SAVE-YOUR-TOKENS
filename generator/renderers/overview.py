"""OVERVIEW.md: repository identity — type, languages and technology stack."""

from __future__ import annotations

from analyzer.models import Detection, Project
from generator import markdown
from generator.models import Document

_DESCRIPTION = "Repository type, languages, frameworks and technology stack."


def render(project: Project) -> Document:
    parts = [markdown.heading("Overview", 1)]

    parts.append(markdown.heading("Repository Type", 2))
    if project.repository_type:
        detected = project.repository_type
        parts.append(
            markdown.paragraph(
                f"{detected.name} (confidence: {detected.confidence.name})"
            )
        )
        if detected.evidence:
            parts.append(
                markdown.bullet_list([markdown.code(e) for e in detected.evidence])
            )
    else:
        parts.append(markdown.paragraph("Not determined."))

    parts.append(markdown.heading("Languages", 2))
    if project.languages:
        rows = [
            [lang.name, f"{lang.percentage:.1f}%", str(lang.file_count)]
            for lang in project.languages
        ]
        parts.append(markdown.table(["Language", "Share", "Files"], rows))
    else:
        parts.append(markdown.paragraph("No recognised languages detected."))

    parts.append(_detection_section("Frameworks", project.frameworks))
    parts.append(_detection_section("Package Managers", project.package_managers))
    parts.append(_detection_section("Build Tools", project.build_tools))
    parts.append(_detection_section("CI/CD", project.ci_providers))
    parts.append(_detection_section("Containerization", project.container_tools))
    parts.append(_detection_section("Environment Surfaces", project.environment_files))

    body = "\n".join(parts)
    return Document("OVERVIEW.md", "Overview", _DESCRIPTION, body)


def _detection_section(title: str, detections: tuple[Detection, ...]) -> str:
    lines = [markdown.heading(title, 2)]
    table_markdown = markdown.detection_table(detections)
    if table_markdown:
        lines.append(table_markdown)
    else:
        lines.append(markdown.paragraph(f"No {title.lower()} detected."))
    return "\n".join(lines)
