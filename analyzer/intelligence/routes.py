"""API route detection for FastAPI, Flask and Django.

FastAPI and Flask both support ``@thing.get("/path")``-style decorators, so
the shortcut-decorator form alone can't tell them apart. The framework label
is decided by which web framework Phase 2 already detected for the project
(``Project.frameworks``) — reusing that result rather than re-guessing it.

Django routes are only read from files named ``urls.py`` — Django's
near-universal convention — rather than scanning every file for calls named
``path``/``re_path``, which could false-positive on unrelated code (see
D-020). Django doesn't declare an HTTP method at the URL-conf level (that's
decided by the view's own method handlers, which is behavior this phase
doesn't interpret), so its routes report method ``"ANY"``.
"""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

from analyzer.intelligence.common import ParsedModule, parse_python_files
from analyzer.models import Project, Route

_SHORTCUT_HTTP_METHODS = frozenset(
    {"get", "post", "put", "delete", "patch", "options", "head"}
)
_DJANGO_PATH_FUNCS = frozenset({"path", "re_path", "url"})


def detect_routes(
    project: Project, *, only: frozenset[str] | None = None
) -> tuple[Route, ...]:
    """Detect routes. ``only`` restricts AST parsing to those files (Phase 6
    incremental re-analysis, D-044); omit it for the full project.
    """
    parsed_modules = parse_python_files(project, only=only)
    framework = _web_framework(project)
    routes: list[Route] = []

    for parsed in parsed_modules:
        routes.extend(_detect_shortcut_routes(parsed, framework))
        routes.extend(_detect_flask_route_decorator(parsed))
        routes.extend(_detect_django_routes(parsed))

    return tuple(
        sorted(routes, key=lambda route: (str(route.file), route.path, route.method))
    )


def _web_framework(project: Project) -> str:
    framework_names = {framework.name for framework in project.frameworks}
    if "FastAPI" in framework_names:
        return "FastAPI"
    if "Flask" in framework_names:
        return "Flask"
    return "Unknown"


def _detect_shortcut_routes(parsed: ParsedModule, framework: str) -> list[Route]:
    routes = []
    for node in ast.walk(parsed.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            route = _shortcut_route(decorator, node.name, parsed.file.path, framework)
            if route:
                routes.append(route)
    return routes


def _shortcut_route(
    decorator: ast.expr, handler: str, file: PurePosixPath, framework: str
) -> Route | None:
    if not isinstance(decorator, ast.Call) or not isinstance(
        decorator.func, ast.Attribute
    ):
        return None
    if decorator.func.attr not in _SHORTCUT_HTTP_METHODS:
        return None
    path = _first_string_arg(decorator)
    if path is None:
        return None
    return Route(decorator.func.attr.upper(), path, handler, file, framework)


def _detect_flask_route_decorator(parsed: ParsedModule) -> list[Route]:
    routes = []
    for node in ast.walk(parsed.tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(
                decorator.func, ast.Attribute
            ):
                continue
            if decorator.func.attr != "route":
                continue
            path = _first_string_arg(decorator)
            if path is None:
                continue
            for method in _methods_keyword(decorator) or ["GET"]:
                routes.append(Route(method, path, node.name, parsed.file.path, "Flask"))
    return routes


def _detect_django_routes(parsed: ParsedModule) -> list[Route]:
    if parsed.file.name != "urls.py":
        return []
    routes = []
    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.Call) or len(node.args) < 2:
            continue
        func_name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else (node.func.attr if isinstance(node.func, ast.Attribute) else None)
        )
        if func_name not in _DJANGO_PATH_FUNCS:
            continue
        pattern = node.args[0]
        if not isinstance(pattern, ast.Constant) or not isinstance(pattern.value, str):
            continue
        handler = ast.unparse(node.args[1])
        routes.append(Route("ANY", pattern.value, handler, parsed.file.path, "Django"))
    return routes


def _first_string_arg(call: ast.Call) -> str | None:
    if (
        call.args
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    ):
        return call.args[0].value
    return None


def _methods_keyword(call: ast.Call) -> list[str] | None:
    for keyword in call.keywords:
        if keyword.arg != "methods" or not isinstance(
            keyword.value, (ast.List, ast.Tuple)
        ):
            continue
        methods = [
            elt.value.upper()
            for elt in keyword.value.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
        if methods:
            return methods
    return None
