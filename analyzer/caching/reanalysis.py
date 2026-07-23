"""Selective re-analysis: reuse cached per-file results for unchanged
files, and re-run analysis only where it's safe and worthwhile.

Four categories are file-local — nothing in ``analyzer.intelligence``'s
extraction of a file's own entry points, module structure, routes or
database models depends on any *other* file's content — so they're merged:
cached results survive for unchanged and renamed files, fresh results (via
the ``only=`` filter added in D-044) replace them for new or modified
files.

Everything else (imports, circular imports, module dependencies,
authentication, configuration, important-file ranking) is recomputed in
full whenever anything changed. Imports specifically were considered for
the same per-file treatment, but a cached edge's correctness depends on
whether its *target* file still exists — which can change even when the
*importing* file didn't (file B, which A imports, can be deleted without
touching A). Safely revalidating a cached edge without re-parsing would
need ``ImportEdge`` to carry structured ``(level, module, name)`` fields
instead of one formatted string, which is exactly the kind of Phase 3
model change this phase avoids unless unavoidable — so imports falls back
to a full pass instead (D-047), using this project's own "if correctness
cannot be guaranteed, fall back to full analysis" rule.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath

from analyzer.caching.models import Cache, ChangeSet, RenamedFile
from analyzer.intelligence.authentication import detect_authentication
from analyzer.intelligence.configuration import detect_configuration
from analyzer.intelligence.database import detect_database_models
from analyzer.intelligence.entrypoints import detect_entry_points
from analyzer.intelligence.importance import rank_important_files
from analyzer.intelligence.imports import analyze_imports, detect_circular_imports
from analyzer.intelligence.modules import analyze_modules
from analyzer.intelligence.relationships import build_module_dependencies
from analyzer.intelligence.routes import detect_routes
from analyzer.models import (
    DatabaseModel,
    EntryPoint,
    ModuleInfo,
    Project,
    Route,
)


def build_project_incrementally(
    project: Project, cache: Cache | None, change_set: ChangeSet
) -> Project:
    """Populate Phase 3 intelligence fields on ``project``, reusing the
    cache wherever safe. ``project`` must already have Phase 1/2 fields
    populated (``scan_repository`` + ``identify_project`` already ran —
    those stay full every run; cheap, and out of this phase's scope).
    """
    if cache is not None and not change_set.has_changes:
        return replace(
            project,
            entry_points=cache.entry_points,
            modules=cache.modules,
            imports=cache.imports,
            circular_imports=cache.circular_imports,
            routes=cache.routes,
            database_models=cache.database_models,
            authentication=cache.authentication,
            configuration=cache.configuration,
            module_dependencies=cache.module_dependencies,
            important_files=cache.important_files,
        )

    entry_points = _merge_entry_points(project, cache, change_set)
    modules = _merge_modules(project, cache, change_set)
    routes = _merge_routes(project, cache, change_set)
    database_models = _merge_database_models(project, cache, change_set)

    # Not safely incremental (see module docstring) — always a full pass
    # once anything has changed.
    imports = analyze_imports(project)
    circular_imports = detect_circular_imports(imports)
    module_dependencies = build_module_dependencies(imports)
    authentication = detect_authentication(project)
    configuration = detect_configuration(project)

    identified = replace(
        project,
        entry_points=entry_points,
        modules=modules,
        imports=imports,
        circular_imports=circular_imports,
        routes=routes,
        database_models=database_models,
        authentication=authentication,
        configuration=configuration,
        module_dependencies=module_dependencies,
    )
    important_files = rank_important_files(
        python_files=identified.files_with_extension(".py"),
        entry_points=entry_points,
        module_dependencies=module_dependencies,
        routes=routes,
        database_models=database_models,
    )
    return replace(identified, important_files=important_files)


def _stale_paths(change_set: ChangeSet) -> frozenset[str]:
    """Files whose cached entries must not survive as-is: reparsed or deleted."""
    return change_set.files_to_reparse | frozenset(
        str(p) for p in change_set.deleted_files
    )


def _rename_map(renames: tuple[RenamedFile, ...]) -> dict[str, PurePosixPath]:
    return {str(renamed.old_path): renamed.new_path for renamed in renames}


def _merge_entry_points(
    project: Project, cache: Cache | None, change_set: ChangeSet
) -> tuple[EntryPoint, ...]:
    only = change_set.files_to_reparse
    fresh = detect_entry_points(project, only=only)
    if cache is None:
        return fresh
    # Django's manage.py entry point is always cheaply redetected by the
    # call above regardless of `only` (filename-based, not AST-based) — so
    # it's dropped from "kept" unconditionally to avoid duplicating it.
    stale = _stale_paths(change_set)
    renames = _rename_map(change_set.renamed_files)
    kept = tuple(
        replace(ep, file=renames[str(ep.file)]) if str(ep.file) in renames else ep
        for ep in cache.entry_points
        if ep.kind != "django_manage" and str(ep.file) not in stale
    )
    return tuple(sorted((*kept, *fresh), key=lambda ep: (str(ep.file), ep.kind)))


def _merge_modules(
    project: Project, cache: Cache | None, change_set: ChangeSet
) -> tuple[ModuleInfo, ...]:
    only = change_set.files_to_reparse
    fresh = analyze_modules(project, only=only)
    if cache is None:
        return fresh
    stale = _stale_paths(change_set)
    renames = _rename_map(change_set.renamed_files)
    kept = tuple(
        replace(module, file=renames[str(module.file)])
        if str(module.file) in renames
        else module
        for module in cache.modules
        if str(module.file) not in stale
    )
    return tuple(sorted((*kept, *fresh), key=lambda module: str(module.file)))


def _merge_routes(
    project: Project, cache: Cache | None, change_set: ChangeSet
) -> tuple[Route, ...]:
    only = change_set.files_to_reparse
    fresh = detect_routes(project, only=only)
    if cache is None:
        return fresh
    stale = _stale_paths(change_set)
    renames = _rename_map(change_set.renamed_files)
    kept = tuple(
        replace(route, file=renames[str(route.file)])
        if str(route.file) in renames
        else route
        for route in cache.routes
        if str(route.file) not in stale
    )
    return tuple(
        sorted(
            (*kept, *fresh),
            key=lambda route: (str(route.file), route.path, route.method),
        )
    )


def _merge_database_models(
    project: Project, cache: Cache | None, change_set: ChangeSet
) -> tuple[DatabaseModel, ...]:
    only = change_set.files_to_reparse
    fresh = detect_database_models(project, only=only)
    if cache is None:
        return fresh
    stale = _stale_paths(change_set)
    renames = _rename_map(change_set.renamed_files)
    kept = tuple(
        replace(model, file=renames[str(model.file)])
        if str(model.file) in renames
        else model
        for model in cache.database_models
        if str(model.file) not in stale
    )
    return tuple(
        sorted((*kept, *fresh), key=lambda model: (str(model.file), model.name))
    )
