"""Per-module structural metadata: classes, functions, constants, exports.

Top-level only — a class's methods or a function's nested helpers aren't
walked here, since this is a map of what a module *exposes*, not a full
symbol table. Never business logic: no function body is inspected.
"""

from __future__ import annotations

import ast

from analyzer.intelligence.common import ParsedModule, parse_python_files
from analyzer.models import ModuleInfo, Project


def analyze_modules(
    project: Project, *, only: frozenset[str] | None = None
) -> tuple[ModuleInfo, ...]:
    """Analyse modules. ``only`` restricts AST parsing to those files
    (Phase 6 incremental re-analysis, D-044); omit it for the full project.
    """
    parsed_modules = parse_python_files(project, only=only)
    return tuple(
        sorted(
            (_analyze_module(parsed) for parsed in parsed_modules),
            key=lambda module: str(module.file),
        )
    )


def _analyze_module(parsed: ParsedModule) -> ModuleInfo:
    classes: list[str] = []
    functions: list[str] = []
    async_functions: list[str] = []
    constants: list[str] = []

    for node in parsed.tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            async_functions.append(node.name)
        elif isinstance(node, ast.Assign):
            constants.extend(
                target.id
                for target in node.targets
                if isinstance(target, ast.Name) and target.id.isupper()
            )
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id.isupper()
        ):
            constants.append(node.target.id)

    declared_exports = _find_dunder_all(parsed.tree)
    exports = declared_exports or tuple(
        name
        for name in classes + functions + async_functions + constants
        if not name.startswith("_")
    )

    return ModuleInfo(
        file=parsed.file.path,
        classes=tuple(sorted(classes)),
        functions=tuple(sorted(functions)),
        async_functions=tuple(sorted(async_functions)),
        constants=tuple(sorted(constants)),
        exports=tuple(sorted(exports)),
    )


def _find_dunder_all(tree: ast.Module) -> tuple[str, ...] | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            continue
        if isinstance(node.value, (ast.List, ast.Tuple)):
            return tuple(
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            )
    return None
