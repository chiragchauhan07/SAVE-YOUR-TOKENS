"""Minimal Markdown-building helpers.

Plain string formatting, not a template engine — Knowledge Base generation
is straightforward structured-data-to-Markdown assembly, not nested
templating, so a templating dependency would be unjustified (D-026).
"""

from __future__ import annotations

from collections.abc import Sequence

from analyzer.models import Detection


def heading(text: str, level: int = 1) -> str:
    return f"{'#' * level} {text}\n"


def paragraph(text: str) -> str:
    return f"{text}\n"


def bullet_list(items: Sequence[str]) -> str:
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items) + "\n"


def code(text: str) -> str:
    return f"`{_escape_inline(text)}`"


def table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join("---" for _ in headers) + " |"
    row_lines = [
        "| " + " | ".join(_escape_cell(str(cell)) for cell in row) + " |"
        for row in rows
    ]
    return "\n".join([header_line, separator_line, *row_lines]) + "\n"


def detection_table(detections: tuple[Detection, ...]) -> str:
    """A Name/Confidence/Evidence table for a tuple of Detections.

    Returns an empty string when there are none — callers supply their own
    "none detected" message, since the right wording differs per section.
    """
    if not detections:
        return ""
    rows = [[d.name, d.confidence.name, "; ".join(d.evidence)] for d in detections]
    return table(["Name", "Confidence", "Evidence"], rows)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _escape_inline(value: str) -> str:
    return value.replace("`", "'")
