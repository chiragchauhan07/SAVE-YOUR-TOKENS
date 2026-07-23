"""Which ``Project`` fields each generated document's content depends on.

Data, not logic — same "rules as data" principle as
``analyzer/detectors/signatures.py`` and ``generator/navigation.py``. Used
only for the change report's human-readable "why did X change" — the
correctness of what actually gets *written* never depends on this map
(that comes from ``generator.writer.write_documents_if_changed`` comparing
rendered content to disk directly, which stays right even if this map
were ever incomplete).
"""

from __future__ import annotations

DOCUMENT_FIELDS: dict[str, frozenset[str]] = {
    "OVERVIEW.md": frozenset(
        {
            "repository_type",
            "languages",
            "frameworks",
            "package_managers",
            "build_tools",
            "ci_providers",
            "container_tools",
            "environment_files",
        }
    ),
    "PROJECT_STRUCTURE.md": frozenset({"stats"}),
    "ARCHITECTURE.md": frozenset(
        {
            "entry_points",
            "important_files",
            "imports",
            "module_dependencies",
            "circular_imports",
        }
    ),
    "MODULES.md": frozenset({"modules"}),
    "DEPENDENCIES.md": frozenset(
        {"imports", "circular_imports", "module_dependencies"}
    ),
    "API_ROUTES.md": frozenset({"routes"}),
    "DATABASE.md": frozenset({"database_models"}),
    "AUTHENTICATION.md": frozenset({"authentication"}),
    "CONFIGURATION.md": frozenset({"configuration", "environment_files"}),
    "IMPORTANT_FILES.md": frozenset({"important_files"}),
    "AI_CONTEXT.md": frozenset(
        {
            "repository_type",
            "entry_points",
            "routes",
            "database_models",
            "authentication",
            "configuration",
            "important_files",
        }
    ),
    "INDEX.md": frozenset(),
}
