"""Database model detection: SQLAlchemy, Pydantic and Django ORM.

Every classification requires a specific, well-known base class name — a
bare, unqualified ``class Foo(Model):`` with no recognisable qualifier is
not classified as anything, since a bare ``Model`` name alone is genuinely
ambiguous (never guess). Fields are read from class-level assignments only;
no method body is inspected.
"""

from __future__ import annotations

import ast
from pathlib import PurePosixPath

from analyzer.intelligence.common import parse_python_files, qualifier_name, simple_name
from analyzer.models import DatabaseModel, Project

_SQLALCHEMY_BASE_NAMES = frozenset({"Base", "DeclarativeBase"})
_SQLALCHEMY_FIELD_CALLS = frozenset({"Column", "mapped_column"})


def detect_database_models(
    project: Project, *, only: frozenset[str] | None = None
) -> tuple[DatabaseModel, ...]:
    """Detect database models. ``only`` restricts AST parsing to those files
    (Phase 6 incremental re-analysis, D-044); omit it for the full project.
    """
    parsed_modules = parse_python_files(project, only=only)
    models: list[DatabaseModel] = []
    for parsed in parsed_modules:
        for node in ast.walk(parsed.tree):
            if isinstance(node, ast.ClassDef):
                model = _classify_model(node, parsed.file.path)
                if model:
                    models.append(model)
    return tuple(sorted(models, key=lambda model: (str(model.file), model.name)))


def _classify_model(node: ast.ClassDef, file: PurePosixPath) -> DatabaseModel | None:
    for base in node.bases:
        name = simple_name(base)
        qualifier = qualifier_name(base)
        if name == "BaseModel":
            return _build_pydantic_model(node, file)
        if name == "Model" and qualifier == "models":
            return _build_django_model(node, file)
        if name == "Model" and qualifier == "db":
            return _build_sqlalchemy_model(node, file, base_repr="db.Model")
        if name in _SQLALCHEMY_BASE_NAMES:
            return _build_sqlalchemy_model(node, file, base_repr=name)
    return None


def _build_pydantic_model(node: ast.ClassDef, file: PurePosixPath) -> DatabaseModel:
    fields = tuple(
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign)
        and isinstance(item.target, ast.Name)
        and not item.target.id.startswith("_")
    )
    return DatabaseModel(
        node.name, "Pydantic", None, file, fields, ("inherits BaseModel",)
    )


def _build_django_model(node: ast.ClassDef, file: PurePosixPath) -> DatabaseModel:
    fields = []
    for item in node.body:
        if not isinstance(item, ast.Assign) or not isinstance(item.value, ast.Call):
            continue
        name = _assign_target(item)
        if name and not name.startswith("_"):
            fields.append(name)
    return DatabaseModel(
        node.name, "Django ORM", None, file, tuple(fields), ("inherits models.Model",)
    )


def _build_sqlalchemy_model(
    node: ast.ClassDef, file: PurePosixPath, base_repr: str
) -> DatabaseModel:
    fields = []
    table_name = None
    for item in node.body:
        if isinstance(item, ast.Assign) and _assign_target(item) == "__tablename__":
            if isinstance(item.value, ast.Constant) and isinstance(
                item.value.value, str
            ):
                table_name = item.value.value
            continue
        if isinstance(item, ast.Assign) and isinstance(item.value, ast.Call):
            name = _assign_target(item)
            if name and simple_name(item.value.func) in _SQLALCHEMY_FIELD_CALLS:
                fields.append(name)
        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            if (
                isinstance(item.annotation, ast.Subscript)
                and simple_name(item.annotation.value) == "Mapped"
            ):
                fields.append(item.target.id)
    return DatabaseModel(
        node.name,
        "SQLAlchemy",
        table_name,
        file,
        tuple(fields),
        (f"inherits {base_repr}",),
    )


def _assign_target(node: ast.Assign) -> str | None:
    if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None
