"""Important-file ranking: evidence-based, never repository-specific names.

Score is a sum of independent, named signals — import fan-in, presence as
an entry point, presence of detected routes/database models, and well-known
file-name/directory conventions (settings, models, routers, services, api).
No file name specific to any one project is ever special-cased; the
conventions here apply to any Python repository.
"""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from analyzer.models import (
    DatabaseModel,
    EntryPoint,
    FileInfo,
    ImportantFile,
    ModuleDependency,
    Route,
)

#: Each signal is capped so no single dimension can dominate the score of a
#: file that happens to score very high on just one axis (e.g. a utility
#: module imported by fifty files but otherwise unremarkable).
_MAX_SIGNAL_CONTRIBUTION = 5

_CONVENTIONAL_FILENAMES = frozenset(
    {
        "settings.py",
        "config.py",
        "database.py",
        "db.py",
        "models.py",
        "auth.py",
        "authentication.py",
        "api.py",
        "routes.py",
        "urls.py",
        "main.py",
        "app.py",
    }
)
_CONVENTIONAL_DIRECTORIES = frozenset({"routers", "models", "services", "api", "core"})


def rank_important_files(
    *,
    python_files: tuple[FileInfo, ...],
    entry_points: tuple[EntryPoint, ...],
    module_dependencies: tuple[ModuleDependency, ...],
    routes: tuple[Route, ...],
    database_models: tuple[DatabaseModel, ...],
) -> tuple[ImportantFile, ...]:
    fan_in: Counter[str] = Counter(str(dep.target) for dep in module_dependencies)
    route_counts: Counter[str] = Counter(str(route.file) for route in routes)
    model_counts: Counter[str] = Counter(str(model.file) for model in database_models)
    entry_files = {str(ep.file) for ep in entry_points}

    # Every Python file is a candidate — not just ones with an import/route/
    # model signal — so a zero-fan-in file like an unimported config.py can
    # still surface on its filename convention alone.
    all_files = {str(file.path) for file in python_files} | entry_files
    ranked = [
        scored
        for file in sorted(all_files)
        if (
            scored := _score_file(file, entry_files, fan_in, route_counts, model_counts)
        )
    ]
    return tuple(sorted(ranked, key=lambda f: (-f.score, str(f.file))))


def _score_file(
    file: str,
    entry_files: set[str],
    fan_in: Counter[str],
    route_counts: Counter[str],
    model_counts: Counter[str],
) -> ImportantFile | None:
    score = 0
    reasons: list[str] = []

    if file in entry_files:
        score += _MAX_SIGNAL_CONTRIBUTION
        reasons.append("entry point")

    imported_by = fan_in.get(file, 0)
    if imported_by:
        score += min(imported_by, _MAX_SIGNAL_CONTRIBUTION)
        reasons.append(f"imported by {imported_by} internal module(s)")

    routes_here = route_counts.get(file, 0)
    if routes_here:
        score += min(routes_here, _MAX_SIGNAL_CONTRIBUTION)
        reasons.append(f"defines {routes_here} route(s)")

    models_here = model_counts.get(file, 0)
    if models_here:
        score += min(models_here, _MAX_SIGNAL_CONTRIBUTION)
        reasons.append(f"defines {models_here} database model(s)")

    path = PurePosixPath(file)
    if path.name in _CONVENTIONAL_FILENAMES:
        score += 2
        reasons.append(f"conventional file name: {path.name}")

    if _CONVENTIONAL_DIRECTORIES & set(path.parts[:-1]):
        score += 1
        reasons.append("conventional directory")

    if not score:
        return None
    return ImportantFile(path, score, tuple(reasons))
