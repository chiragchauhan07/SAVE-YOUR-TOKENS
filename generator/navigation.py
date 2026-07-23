"""Cross-reference ("Related Context") links between Knowledge Base files.

The adjacency table is data, not logic — same principle as
``analyzer/constants.py`` (D-006) and ``analyzer/detectors/signatures.py``.
Every key and every value must be a real generated filename; checked by
``tests/test_generator.py::test_related_context_links_are_valid``.
"""

from __future__ import annotations

RELATED_DOCUMENTS: dict[str, tuple[str, ...]] = {
    "OVERVIEW.md": ("ARCHITECTURE.md", "PROJECT_STRUCTURE.md", "DEPENDENCIES.md"),
    "PROJECT_STRUCTURE.md": ("OVERVIEW.md", "IMPORTANT_FILES.md"),
    "ARCHITECTURE.md": (
        "IMPORTANT_FILES.md",
        "DEPENDENCIES.md",
        "MODULES.md",
        "OVERVIEW.md",
    ),
    "MODULES.md": ("DEPENDENCIES.md", "ARCHITECTURE.md"),
    "DEPENDENCIES.md": ("MODULES.md", "ARCHITECTURE.md", "IMPORTANT_FILES.md"),
    "API_ROUTES.md": ("AUTHENTICATION.md", "MODULES.md", "ARCHITECTURE.md"),
    "DATABASE.md": ("MODULES.md", "CONFIGURATION.md"),
    "AUTHENTICATION.md": ("API_ROUTES.md", "CONFIGURATION.md"),
    "CONFIGURATION.md": ("AUTHENTICATION.md", "DATABASE.md", "OVERVIEW.md"),
    "IMPORTANT_FILES.md": ("ARCHITECTURE.md", "DEPENDENCIES.md"),
    "AI_CONTEXT.md": ("INDEX.md", "OVERVIEW.md", "ARCHITECTURE.md"),
    "INDEX.md": ("AI_CONTEXT.md",),
}


def render_related_context(filename: str, descriptions: dict[str, str]) -> str:
    """The '## Related Context' footer for one document, or "" if it has none."""
    targets = RELATED_DOCUMENTS.get(filename, ())
    if not targets:
        return ""
    lines = [f"- [{target}]({target}) — {descriptions[target]}" for target in targets]
    return "\n## Related Context\n\n" + "\n".join(lines) + "\n"
