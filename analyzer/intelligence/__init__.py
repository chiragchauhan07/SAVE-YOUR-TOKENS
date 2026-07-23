"""Phase 3: understand a repository's internal Python structure.

Builds on the Phase 1 scan and Phase 2 identification — route and
configuration detection read ``Project.frameworks`` and
``Project.environment_files``, so ``analyze_intelligence()`` must run after
``identify_project()``. Everything here is deterministic Python AST
analysis: no source execution, no imports of the analyzed project, no eval
(D-018). A syntax error in one file is skipped, never fatal to the rest of
the analysis (see ``analyzer.intelligence.common``).

Python only for now. Adding a second language means adding a new sibling
package following the same shape (one function per concern, ``Project`` in,
typed results out) — nothing here needs to change.
"""

from __future__ import annotations

from dataclasses import replace

from analyzer.intelligence.authentication import detect_authentication
from analyzer.intelligence.configuration import detect_configuration
from analyzer.intelligence.database import detect_database_models
from analyzer.intelligence.entrypoints import detect_entry_points
from analyzer.intelligence.importance import rank_important_files
from analyzer.intelligence.imports import analyze_imports, detect_circular_imports
from analyzer.intelligence.modules import analyze_modules
from analyzer.intelligence.relationships import build_module_dependencies
from analyzer.intelligence.routes import detect_routes
from analyzer.models import Project

__all__ = ["analyze_intelligence"]


def analyze_intelligence(project: Project) -> Project:
    """Run every Phase 3 module and return the project with the results attached.

    Assumes ``identify_project()`` has already run.
    """
    imports = analyze_imports(project)
    module_dependencies = build_module_dependencies(imports)
    routes = detect_routes(project)
    database_models = detect_database_models(project)
    entry_points = detect_entry_points(project)

    return replace(
        project,
        entry_points=entry_points,
        modules=analyze_modules(project),
        imports=imports,
        circular_imports=detect_circular_imports(imports),
        routes=routes,
        database_models=database_models,
        authentication=detect_authentication(project),
        configuration=detect_configuration(project),
        module_dependencies=module_dependencies,
        important_files=rank_important_files(
            python_files=project.files_with_extension(".py"),
            entry_points=entry_points,
            module_dependencies=module_dependencies,
            routes=routes,
            database_models=database_models,
        ),
    )
