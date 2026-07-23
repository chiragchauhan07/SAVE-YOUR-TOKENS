"""Response-shaping helpers shared by more than one tool.

No MCP SDK imports here, and no analysis logic — only reuses
``analyzer.serialization`` to build the compact shapes the tools return.
Keeping this separate from ``handlers.py`` is what lets
``build_repository_summary`` serve both ``analyze_repository`` and
``repository_summary`` without duplicating the shaping logic (D-036).
"""

from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version

from analyzer import __version__ as ENGINE_VERSION
from analyzer.models import Project
from analyzer.serialization import (
    database_model_dict,
    detection_dict,
    entry_point_dict,
    important_file_dict,
    language_dict,
    route_dict,
)

#: Repository summaries cap the important-files list — the full ranking is
#: always available via the generated IMPORTANT_FILES.md, and an MCP
#: response payload should stay compact (Performance requirements).
_SUMMARY_IMPORTANT_FILES = 20


def build_repository_summary(project: Project) -> dict[str, object]:
    """The compact overview shape: type, stack, entry points, routes,
    models, important files, authentication, configuration.
    """
    return {
        "name": project.name,
        "path": str(project.root),
        "repository_type": (
            detection_dict(project.repository_type) if project.repository_type else None
        ),
        "languages": [language_dict(language) for language in project.languages],
        "frameworks": [detection_dict(d) for d in project.frameworks],
        "entry_points": [entry_point_dict(ep) for ep in project.entry_points],
        "routes": [route_dict(r) for r in project.routes],
        "database_models": [database_model_dict(m) for m in project.database_models],
        "important_files": [
            important_file_dict(f)
            for f in project.important_files[:_SUMMARY_IMPORTANT_FILES]
        ],
        "authentication": [detection_dict(d) for d in project.authentication],
        "configuration": [detection_dict(d) for d in project.configuration],
    }


def build_health_status() -> dict[str, object]:
    """Package, SDK and environment versions — for diagnosing installations."""
    return {
        "status": "ok",
        "package_version": ENGINE_VERSION,
        "server_version": ENGINE_VERSION,
        "mcp_sdk_version": _safe_installed_version("mcp"),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def _safe_installed_version(distribution_name: str) -> str | None:
    try:
        return installed_version(distribution_name)
    except PackageNotFoundError:
        return None
