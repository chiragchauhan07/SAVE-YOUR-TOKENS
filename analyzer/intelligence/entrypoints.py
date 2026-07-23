"""Application entry point detection.

Every kind requires direct AST/filename evidence — a file merely named
``main.py`` with no ``if __name__ == "__main__":`` guard and no framework
app object is not reported as an entry point. A name match alone is a hint,
never proof.
"""

from __future__ import annotations

import ast

from analyzer.intelligence.common import ParsedModule, parse_python_files, simple_name
from analyzer.models import Confidence, EntryPoint, Project

_CONVENTIONAL_SCRIPT_NAMES = frozenset({"main.py", "app.py", "run.py"})


def detect_entry_points(
    project: Project, *, only: frozenset[str] | None = None
) -> tuple[EntryPoint, ...]:
    """Detect entry points. ``only`` restricts AST parsing to those files
    (Phase 6 incremental re-analysis, D-044); omit it for the full project.
    """
    parsed_modules = parse_python_files(project, only=only)
    entry_points: list[EntryPoint] = []

    for parsed in parsed_modules:
        entry_points.extend(_detect_app_objects(parsed))
        guard = _detect_main_guard(parsed)
        if guard:
            entry_points.append(guard)

    entry_points.extend(
        EntryPoint(
            file.path, "django_manage", None, Confidence.HIGH, ("file: manage.py",)
        )
        for file in project.find("manage.py")
    )

    return tuple(sorted(entry_points, key=lambda ep: (str(ep.file), ep.kind)))


def _detect_app_objects(parsed: ParsedModule) -> list[EntryPoint]:
    entry_points = []
    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        callee = simple_name(node.value.func)
        if callee not in {"FastAPI", "Flask"}:
            continue
        target = node.targets[0] if len(node.targets) == 1 else None
        symbol = target.id if isinstance(target, ast.Name) else None
        evidence = [f"{callee}() call in {parsed.file.path}"]
        kind = "fastapi_app" if callee == "FastAPI" else "flask_app"
        if kind == "fastapi_app" and symbol:
            evidence.extend(_fastapi_corroborating_evidence(parsed.tree, symbol))
        entry_points.append(
            EntryPoint(parsed.file.path, kind, symbol, Confidence.HIGH, tuple(evidence))
        )
    return entry_points


def _fastapi_corroborating_evidence(tree: ast.Module, app_symbol: str) -> list[str]:
    evidence = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "run" and simple_name(node.func.value) == "uvicorn":
            evidence.append("uvicorn.run() call")
        elif (
            node.func.attr == "include_router"
            and simple_name(node.func.value) == app_symbol
        ):
            evidence.append(f"{app_symbol}.include_router() call")
    return evidence


def _detect_main_guard(parsed: ParsedModule) -> EntryPoint | None:
    for node in ast.walk(parsed.tree):
        if _is_main_guard(node):
            evidence = ["if __name__ == '__main__' guard"]
            if parsed.file.name in _CONVENTIONAL_SCRIPT_NAMES:
                evidence.append(f"conventional entry filename: {parsed.file.name}")
            return EntryPoint(
                parsed.file.path, "script", None, Confidence.HIGH, tuple(evidence)
            )
    return None


def _is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    is_dunder_name = isinstance(left, ast.Name) and left.id == "__name__"
    is_main_string = isinstance(right, ast.Constant) and right.value == "__main__"
    return is_dunder_name and is_main_string
