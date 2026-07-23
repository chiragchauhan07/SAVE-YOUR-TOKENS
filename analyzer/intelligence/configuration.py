"""Configuration surface detection: settings modules, config classes,
environment-variable loading and dotenv usage.

Presence only — no secret value is ever read. Complements Phase 2's
``environment_detector`` (which finds ``.env.example``-style files by name)
with source-level signals: what actually loads configuration, not just
which config files exist.
"""

from __future__ import annotations

import ast

from analyzer.intelligence.common import (
    ParsedModule,
    parse_python_files,
    qualifier_name,
    simple_name,
)
from analyzer.models import Confidence, Detection, Project

_SETTINGS_FILENAMES = frozenset({"settings.py", "config.py", "configuration.py"})
_SETTINGS_CLASS_NAMES = frozenset({"Config", "Settings"})


def detect_configuration(project: Project) -> tuple[Detection, ...]:
    parsed_modules = parse_python_files(project)
    evidence: dict[str, list[str]] = {}

    for file in project.files:
        if file.name in _SETTINGS_FILENAMES:
            evidence.setdefault("Settings Module", []).append(f"file: {file.path}")

    for parsed in parsed_modules:
        _collect_config_class_evidence(parsed, evidence)
        _collect_env_loading_evidence(parsed, evidence)
        _collect_dotenv_evidence(parsed, evidence)

    if project.environment_files:
        evidence.setdefault("dotenv usage", []).extend(
            f"file: {detection.name}" for detection in project.environment_files
        )

    return tuple(
        Detection(name, Confidence.HIGH, tuple(dict.fromkeys(lines)))
        for name, lines in sorted(evidence.items())
    )


def _collect_config_class_evidence(
    parsed: ParsedModule, evidence: dict[str, list[str]]
) -> None:
    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {simple_name(base) for base in node.bases}
        if "BaseSettings" in base_names:
            evidence.setdefault("Config Class", []).append(
                f"class {node.name}(BaseSettings) in {parsed.file.path}"
            )
        elif node.name in _SETTINGS_CLASS_NAMES:
            evidence.setdefault("Config Class", []).append(
                f"class {node.name} in {parsed.file.path}"
            )


def _collect_env_loading_evidence(
    parsed: ParsedModule, evidence: dict[str, list[str]]
) -> None:
    for node in ast.walk(parsed.tree):
        is_os_environ = (
            isinstance(node, ast.Attribute)
            and node.attr == "environ"
            and simple_name(node.value) == "os"
        )
        is_os_getenv = (
            isinstance(node, ast.Call)
            and simple_name(node.func) == "getenv"
            and qualifier_name(node.func) == "os"
        )
        if is_os_environ:
            evidence.setdefault("Environment Loading", []).append(
                f"os.environ usage in {parsed.file.path}"
            )
        elif is_os_getenv:
            evidence.setdefault("Environment Loading", []).append(
                f"os.getenv() call in {parsed.file.path}"
            )


def _collect_dotenv_evidence(
    parsed: ParsedModule, evidence: dict[str, list[str]]
) -> None:
    for node in ast.walk(parsed.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "dotenv":
                    evidence.setdefault("dotenv usage", []).append(
                        f"import: {alias.name} in {parsed.file.path}"
                    )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.split(".")[0] == "dotenv"
        ):
            evidence.setdefault("dotenv usage", []).append(
                f"from {node.module} import ... in {parsed.file.path}"
            )
