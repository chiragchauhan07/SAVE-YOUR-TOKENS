"""Overall repository classification.

Combines every other detector's output into one label — "what kind of
project is this". Rules run in a fixed priority order and the first one
with evidence wins: structural signals (monorepo, mobile) before framework
composition (full stack / API / frontend) before packaging signals
(CLI tool / library) before dependency-only signals (AI / ML). See
docs/DECISIONS.md for why a single priority-ordered label was chosen over a
compound tag set.

Must run after detect_frameworks(): it reads ``project.frameworks``.
"""

from __future__ import annotations

import json
import tomllib

from analyzer.detectors import manifests, signatures
from analyzer.models import Confidence, Detection, Project

_WEB_FRAMEWORK_NAMES = (
    signatures.BACKEND_FRAMEWORK_NAMES
    | signatures.FRONTEND_FRAMEWORK_NAMES
    | signatures.FULLSTACK_META_FRAMEWORK_NAMES
)
_BACKEND_CAPABLE_NAMES = (
    signatures.BACKEND_FRAMEWORK_NAMES | signatures.FULLSTACK_META_FRAMEWORK_NAMES
)
_FRONTEND_CAPABLE_NAMES = (
    signatures.FRONTEND_FRAMEWORK_NAMES | signatures.FULLSTACK_META_FRAMEWORK_NAMES
)


def classify_repository(project: Project) -> Detection:
    monorepo_evidence = _monorepo_evidence(project)
    if monorepo_evidence:
        return Detection("Monorepo", Confidence.HIGH, monorepo_evidence)

    framework_names = {framework.name for framework in project.frameworks}
    if "Flutter" in framework_names:
        return Detection("Mobile App", Confidence.HIGH, ("framework: Flutter",))

    has_backend = bool(framework_names & _BACKEND_CAPABLE_NAMES)
    has_frontend = bool(framework_names & _FRONTEND_CAPABLE_NAMES)
    framework_evidence = tuple(
        f"framework: {name}" for name in sorted(framework_names & _WEB_FRAMEWORK_NAMES)
    )

    ai_evidence = _dependency_evidence(project, signatures.AI_DEPENDENCY_MARKERS)
    ml_evidence = _dependency_evidence(project, signatures.ML_DEPENDENCY_MARKERS)
    is_ai_flavoured = bool(ai_evidence or ml_evidence)
    ai_label = "AI" if ai_evidence else "Machine Learning"

    if has_backend and has_frontend:
        label = (
            f"Full Stack {ai_label} Web Application"
            if is_ai_flavoured
            else "Full Stack Web Application"
        )
        evidence = framework_evidence + ai_evidence + ml_evidence
        return Detection(label, Confidence.HIGH, evidence)

    if has_backend:
        label = f"{ai_label} REST API" if is_ai_flavoured else "REST API"
        evidence = framework_evidence + ai_evidence + ml_evidence
        return Detection(label, Confidence.HIGH, evidence)

    if has_frontend:
        return Detection("Frontend Application", Confidence.HIGH, framework_evidence)

    if is_ai_flavoured:
        label = "AI Project" if ai_evidence else "Machine Learning Project"
        return Detection(label, Confidence.MEDIUM, ai_evidence + ml_evidence)

    cli_evidence = _cli_tool_evidence(project)
    if cli_evidence:
        return Detection("CLI Tool", Confidence.MEDIUM, cli_evidence)

    library_evidence = _python_library_evidence(project)
    if library_evidence:
        return Detection("Python Library", Confidence.MEDIUM, library_evidence)

    unknown_evidence = ("no structural or dependency evidence matched",)
    return Detection("Unknown", Confidence.LOW, unknown_evidence)


def _monorepo_evidence(project: Project) -> tuple[str, ...]:
    file_evidence = tuple(
        f"file: {filename}"
        for filename in signatures.MONOREPO_MARKER_FILES
        if project.find(filename)
    )
    if file_evidence:
        return file_evidence

    text = manifests.read_text(project, "package.json")
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and "workspaces" in data:
            return ("file: package.json (workspaces)",)
    return ()


def _dependency_evidence(project: Project, markers: frozenset[str]) -> tuple[str, ...]:
    matched = sorted(manifests.python_dependencies(project) & markers)
    return tuple(f"dependency: {name}" for name in matched)


def _cli_tool_evidence(project: Project) -> tuple[str, ...]:
    text = manifests.read_text(project, "pyproject.toml")
    if not text:
        return ()
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return ()
    has_scripts = bool(manifests.dig(data, "project", "scripts")) or bool(
        manifests.dig(data, "tool", "poetry", "scripts")
    )
    return ("file: pyproject.toml (script entry points)",) if has_scripts else ()


def _python_library_evidence(project: Project) -> tuple[str, ...]:
    evidence = []
    text = manifests.read_text(project, "pyproject.toml")
    if text and "[build-system]" in text:
        evidence.append("file: pyproject.toml ([build-system])")
    if project.find("setup.py"):
        evidence.append("file: setup.py")
    return tuple(evidence)
