"""JSON-serialisable conversions for ``Project`` and its parts.

Extracted from ``cli.py``'s original private helpers so the CLI and the MCP
server (Phase 5) share one conversion implementation instead of two — see
D-034. Every function here is a pure, allocation-only mapping from a frozen
dataclass to plain dicts/lists/strings; none of it reads a file, analyses
anything, or has side effects.
"""

from __future__ import annotations

from analyzer.models import (
    DatabaseModel,
    Detection,
    EntryPoint,
    ImportantFile,
    ImportEdge,
    LanguageStat,
    ModuleDependency,
    ModuleInfo,
    Project,
    Route,
)


def detection_dict(detection: Detection) -> dict:
    return {
        "name": detection.name,
        "confidence": detection.confidence.name,
        "evidence": list(detection.evidence),
    }


def language_dict(language: LanguageStat) -> dict:
    return {
        "name": language.name,
        "file_count": language.file_count,
        "size_bytes": language.size_bytes,
        "percentage": language.percentage,
    }


def entry_point_dict(entry_point: EntryPoint) -> dict:
    return {
        "file": str(entry_point.file),
        "kind": entry_point.kind,
        "symbol": entry_point.symbol,
        "confidence": entry_point.confidence.name,
        "evidence": list(entry_point.evidence),
    }


def route_dict(route: Route) -> dict:
    return {
        "method": route.method,
        "path": route.path,
        "handler": route.handler,
        "file": str(route.file),
        "framework": route.framework,
    }


def database_model_dict(model: DatabaseModel) -> dict:
    return {
        "name": model.name,
        "orm": model.orm,
        "table_name": model.table_name,
        "file": str(model.file),
        "fields": list(model.fields),
        "evidence": list(model.evidence),
    }


def module_dict(module: ModuleInfo) -> dict:
    return {
        "file": str(module.file),
        "classes": list(module.classes),
        "functions": list(module.functions),
        "async_functions": list(module.async_functions),
        "constants": list(module.constants),
        "exports": list(module.exports),
    }


def import_edge_dict(edge: ImportEdge) -> dict:
    return {
        "file": str(edge.file),
        "module": edge.module,
        "is_internal": edge.is_internal,
        "resolved_file": str(edge.resolved_file) if edge.resolved_file else None,
    }


def module_dependency_dict(dependency: ModuleDependency) -> dict:
    return {"source": str(dependency.source), "target": str(dependency.target)}


def important_file_dict(important_file: ImportantFile) -> dict:
    return {
        "file": str(important_file.file),
        "score": important_file.score,
        "reasons": list(important_file.reasons),
    }


def project_to_dict(project: Project) -> dict:
    """The complete JSON representation of a ``Project`` — every field."""
    stats = project.stats
    return {
        "name": project.name,
        "root": str(project.root),
        "repository_type": (
            detection_dict(project.repository_type) if project.repository_type else None
        ),
        "languages": [language_dict(lang) for lang in project.languages],
        "frameworks": [detection_dict(d) for d in project.frameworks],
        "package_managers": [detection_dict(d) for d in project.package_managers],
        "build_tools": [detection_dict(d) for d in project.build_tools],
        "ci_providers": [detection_dict(d) for d in project.ci_providers],
        "container_tools": [detection_dict(d) for d in project.container_tools],
        "environment_files": [detection_dict(d) for d in project.environment_files],
        "entry_points": [entry_point_dict(ep) for ep in project.entry_points],
        "modules": [module_dict(m) for m in project.modules],
        "imports": [import_edge_dict(edge) for edge in project.imports],
        "circular_imports": [list(cycle) for cycle in project.circular_imports],
        "routes": [route_dict(r) for r in project.routes],
        "database_models": [database_model_dict(m) for m in project.database_models],
        "authentication": [detection_dict(d) for d in project.authentication],
        "configuration": [detection_dict(d) for d in project.configuration],
        "module_dependencies": [
            module_dependency_dict(dep) for dep in project.module_dependencies
        ],
        "important_files": [important_file_dict(f) for f in project.important_files],
        "stats": {
            "total_files": stats.total_files,
            "total_directories": stats.total_directories,
            "total_size_bytes": stats.total_size_bytes,
            "files_by_extension": stats.files_by_extension,
            "largest_files": [
                {"path": str(file.path), "size_bytes": file.size_bytes}
                for file in stats.largest_files
            ],
        },
        "files": [
            {
                "path": str(file.path),
                "size_bytes": file.size_bytes,
                "extension": file.extension,
            }
            for file in project.files
        ],
    }
