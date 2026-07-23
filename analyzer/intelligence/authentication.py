"""Authentication mechanism detection.

Every signal is a specific, well-known class, module or convention —
``OAuth2PasswordBearer``, ``jwt`` imports, ``flask_login``, Django's
``MIDDLEWARE`` list. Nothing is inferred from generic patterns like "a
function named ``login``" — that would be guessing at business logic, which
this phase avoids. Reuses ``analyzer.detectors.manifests.python_dependencies``
(Phase 2) as corroborating evidence rather than re-deriving it.
"""

from __future__ import annotations

import ast

from analyzer.detectors import manifests as manifest_reader
from analyzer.intelligence.common import ParsedModule, parse_python_files, simple_name
from analyzer.models import Confidence, Detection, Project

_JWT_MODULES = frozenset({"jwt", "jose"})
_OAUTH_SECURITY_CLASSES = frozenset(
    {"OAuth2PasswordBearer", "OAuth2AuthorizationCodeBearer", "OAuth2"}
)
_API_KEY_SECURITY_CLASSES = frozenset({"APIKeyHeader", "APIKeyQuery", "APIKeyCookie"})
_BEARER_SECURITY_CLASSES = frozenset({"HTTPBearer", "HTTPBasic", "HTTPDigest"})
_JWT_DEPENDENCY_NAMES = frozenset({"pyjwt", "python-jose", "authlib"})
_OAUTH_DEPENDENCY_NAMES = frozenset({"authlib", "oauthlib", "requests-oauthlib"})
_SESSION_DEPENDENCY_NAMES = frozenset({"flask-login"})


def detect_authentication(project: Project) -> tuple[Detection, ...]:
    parsed_modules = parse_python_files(project)
    evidence: dict[str, list[str]] = {}

    for parsed in parsed_modules:
        _collect_import_evidence(parsed, evidence)
        _collect_security_scheme_evidence(parsed, evidence)
        _collect_middleware_evidence(parsed, evidence)
        _collect_django_middleware_evidence(parsed, evidence)

    _collect_dependency_evidence(manifest_reader.python_dependencies(project), evidence)

    return tuple(
        Detection(name, Confidence.HIGH, tuple(dict.fromkeys(lines)))
        for name, lines in sorted(evidence.items())
    )


def _collect_import_evidence(
    parsed: ParsedModule, evidence: dict[str, list[str]]
) -> None:
    for node in ast.walk(parsed.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _record_module_evidence(alias.name, str(parsed.file.path), evidence)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _record_module_evidence(node.module, str(parsed.file.path), evidence)


def _record_module_evidence(
    module: str, file: str, evidence: dict[str, list[str]]
) -> None:
    top_level = module.split(".")[0]
    if top_level in _JWT_MODULES:
        evidence.setdefault("JWT", []).append(f"import: {module} ({file})")
    if top_level == "flask_login":
        evidence.setdefault("Session Authentication", []).append(
            f"import: {module} ({file})"
        )


def _collect_security_scheme_evidence(
    parsed: ParsedModule, evidence: dict[str, list[str]]
) -> None:
    security_vars: dict[str, str] = {}
    file = str(parsed.file.path)

    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        class_name = simple_name(node.value.func)
        if class_name is None:
            continue
        target = node.targets[0] if len(node.targets) == 1 else None
        var_name = target.id if isinstance(target, ast.Name) else None

        if class_name in _OAUTH_SECURITY_CLASSES:
            evidence.setdefault("OAuth", []).append(f"{class_name}() in {file}")
        elif class_name in _API_KEY_SECURITY_CLASSES:
            evidence.setdefault("API Keys", []).append(f"{class_name}() in {file}")
        elif class_name in _BEARER_SECURITY_CLASSES:
            evidence.setdefault("JWT", []).append(f"{class_name}() in {file}")
        else:
            continue
        if var_name:
            security_vars[var_name] = class_name

    if security_vars:
        _collect_depends_evidence(parsed, security_vars, evidence)


def _collect_depends_evidence(
    parsed: ParsedModule, security_vars: dict[str, str], evidence: dict[str, list[str]]
) -> None:
    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.Call) or simple_name(node.func) != "Depends":
            continue
        if not node.args or not isinstance(node.args[0], ast.Name):
            continue
        referenced = node.args[0].id
        if referenced in security_vars:
            evidence.setdefault("FastAPI Depends()", []).append(
                f"Depends({referenced}) in {parsed.file.path}"
            )


def _collect_middleware_evidence(
    parsed: ParsedModule, evidence: dict[str, list[str]]
) -> None:
    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.Call) or simple_name(node.func) != "add_middleware":
            continue
        if not node.args or not isinstance(node.args[0], (ast.Name, ast.Attribute)):
            continue
        middleware_name = simple_name(node.args[0])
        if middleware_name and "auth" in middleware_name.lower():
            evidence.setdefault("Authentication middleware", []).append(
                f"add_middleware({middleware_name}) in {parsed.file.path}"
            )


def _collect_django_middleware_evidence(
    parsed: ParsedModule, evidence: dict[str, list[str]]
) -> None:
    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0] if len(node.targets) == 1 else None
        if not isinstance(target, ast.Name) or target.id != "MIDDLEWARE":
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        for elt in node.value.elts:
            if (
                isinstance(elt, ast.Constant)
                and isinstance(elt.value, str)
                and "auth" in elt.value.lower()
            ):
                evidence.setdefault("Authentication middleware", []).append(
                    f"MIDDLEWARE entry: {elt.value} ({parsed.file.path})"
                )


def _collect_dependency_evidence(
    dependency_names: frozenset[str], evidence: dict[str, list[str]]
) -> None:
    for lib in sorted(_JWT_DEPENDENCY_NAMES & dependency_names):
        evidence.setdefault("JWT", []).append(f"dependency: {lib}")
    for lib in sorted(_OAUTH_DEPENDENCY_NAMES & dependency_names):
        evidence.setdefault("OAuth", []).append(f"dependency: {lib}")
    for lib in sorted(_SESSION_DEPENDENCY_NAMES & dependency_names):
        evidence.setdefault("Session Authentication", []).append(f"dependency: {lib}")
