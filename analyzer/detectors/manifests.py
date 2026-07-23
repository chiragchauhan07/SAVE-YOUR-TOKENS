"""Manifest reading and generic evidence-matching for the Phase 2 detectors.

This is the one place detectors are permitted to read file *content* (D-011
extends the Phase 1 boundary for this reason). It never touches application
source code: only package manifests (``package.json``, ``pyproject.toml``,
...), lockfiles, and well-known configuration file names. No AST, no import
scanning, no business logic.

Three ways a detector can look for something, matched to where it lives:

* ``project.find(name)`` — a non-hidden file the scanner already saw.
* ``path_exists`` / ``any_files_matching`` — a dot-prefixed path the
  scanner's default walk excludes (D-008), checked directly against disk.
* ``read_text`` — a known manifest's content, read directly by path so it
  works whether or not the scanner's filters would have included it.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable
from typing import Any

from analyzer.detectors.signatures import DependencySignature, FileSignature
from analyzer.models import Confidence, Detection, Project

#: Manifests are small by nature; this is a defensive cap, not a real limit.
_MAX_MANIFEST_BYTES = 512_000

_DEPENDENCY_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+")


def read_text(project: Project, relative_path: str) -> str | None:
    """Read a small text file by path relative to the repository root.

    Returns ``None`` for anything that isn't a readable, reasonably-sized
    file — missing, a directory, permission-denied, or oversized. Detectors
    treat absence of evidence as absence of the technology, never an error.
    """
    path = project.root / relative_path
    try:
        if not path.is_file() or path.stat().st_size > _MAX_MANIFEST_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def path_exists(project: Project, relative_path: str) -> str | None:
    """Direct filesystem probe for a dot-prefixed path (see D-008/D-011).

    Returns ``relative_path`` itself (usable directly as evidence) when the
    path exists, else ``None``.
    """
    try:
        exists = (project.root / relative_path).exists()
    except OSError:
        return None
    return relative_path if exists else None


def any_files_matching(
    project: Project, relative_directory: str, suffixes: tuple[str, ...]
) -> str | None:
    """First file with a matching suffix inside a dot-prefixed directory.

    Used for CI configuration directories (``.github/workflows``,
    ``.circleci``) that the scanner's default walk never enters.
    """
    directory = project.root / relative_directory
    try:
        if not directory.is_dir():
            return None
        entries = sorted(directory.iterdir())
    except OSError:
        return None
    for entry in entries:
        if entry.is_file() and entry.suffix.lower() in suffixes:
            return f"{relative_directory}/{entry.name}"
    return None


def match_file_signatures(
    project: Project, signatures: tuple[FileSignature, ...]
) -> list[Detection]:
    """Match tools identified purely by known file names already scanned."""
    detections = []
    for signature in signatures:
        matched_paths = tuple(
            str(file.path)
            for filename in signature.filenames
            for file in project.find(filename)
        )
        if matched_paths:
            detections.append(Detection(signature.name, Confidence.HIGH, matched_paths))
    return detections


def match_dependency_signatures(
    project: Project,
    signatures: tuple[DependencySignature, ...],
    dependency_names: frozenset[str],
) -> list[Detection]:
    """Match frameworks by manifest dependency, falling back to config files.

    A dependency match is HIGH confidence; a config-file-only match is
    MEDIUM. A signature with neither produces no Detection at all.
    """
    detections = []
    for signature in signatures:
        evidence: list[str] = []
        matched_dependency = next(
            (dep for dep in signature.dependency_names if dep in dependency_names), None
        )
        if matched_dependency:
            evidence.append(f"dependency: {matched_dependency}")
        evidence.extend(
            f"file: {config_file}"
            for config_file in signature.config_files
            if project.find(config_file)
        )
        if not evidence:
            continue
        confidence = Confidence.HIGH if matched_dependency else Confidence.MEDIUM
        detections.append(Detection(signature.name, confidence, tuple(evidence)))
    return detections


def merge_detections(detections: Iterable[Detection]) -> tuple[Detection, ...]:
    """Combine same-named detections, keeping all evidence and the best confidence."""
    merged: dict[str, Detection] = {}
    for detection in detections:
        existing = merged.get(detection.name)
        if existing is None:
            merged[detection.name] = detection
            continue
        combined_evidence = existing.evidence + tuple(
            item for item in detection.evidence if item not in existing.evidence
        )
        best_confidence = max(existing.confidence, detection.confidence)
        merged[detection.name] = Detection(
            detection.name, best_confidence, combined_evidence
        )
    return tuple(sorted(merged.values(), key=lambda d: d.name))


def python_dependencies(project: Project) -> frozenset[str]:
    """Dependency names from the root requirements.txt, pyproject.toml or Pipfile.

    Root-level only, deliberately — a nested requirements.txt belongs to a
    subproject (e.g. a fixture app, a sub-package in a monorepo) and must
    not be read as evidence about the repository as a whole.
    """
    names: set[str] = set()
    requirements_text = read_text(project, "requirements.txt")
    if requirements_text:
        names |= _parse_requirements_txt(requirements_text)

    pyproject_text = read_text(project, "pyproject.toml")
    if pyproject_text:
        names |= _parse_pyproject_dependencies(pyproject_text)

    pipfile_text = read_text(project, "Pipfile")
    if pipfile_text:
        names |= _parse_pipfile_dependencies(pipfile_text)

    return frozenset(names)


def node_dependencies(project: Project) -> frozenset[str]:
    """Dependency names declared in the root package.json."""
    text = read_text(project, "package.json")
    if not text:
        return frozenset()
    keys = ("dependencies", "devDependencies", "peerDependencies")
    return _json_dependency_names(text, keys)


def composer_dependencies(project: Project) -> frozenset[str]:
    """Dependency names declared in the root composer.json."""
    text = read_text(project, "composer.json")
    if not text:
        return frozenset()
    return _json_dependency_names(text, ("require", "require-dev"))


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _parse_requirements_txt(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _DEPENDENCY_NAME_RE.match(line)
        if match:
            names.add(_normalize(match.group(0)))
    return names


def dig(data: Any, *keys: str) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _parse_pyproject_dependencies(text: str) -> set[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return set()

    names: set[str] = set()

    for dep in dig(data, "project", "dependencies") or []:
        match = _DEPENDENCY_NAME_RE.match(str(dep))
        if match:
            names.add(_normalize(match.group(0)))

    optional = dig(data, "project", "optional-dependencies")
    if isinstance(optional, dict):
        for group in optional.values():
            if isinstance(group, list):
                for dep in group:
                    match = _DEPENDENCY_NAME_RE.match(str(dep))
                    if match:
                        names.add(_normalize(match.group(0)))

    poetry_deps = dig(data, "tool", "poetry", "dependencies")
    if isinstance(poetry_deps, dict):
        names |= {_normalize(key) for key in poetry_deps if key.lower() != "python"}

    poetry_groups = dig(data, "tool", "poetry", "group")
    if isinstance(poetry_groups, dict):
        for group in poetry_groups.values():
            group_deps = dig(group, "dependencies") if isinstance(group, dict) else None
            if isinstance(group_deps, dict):
                names |= {_normalize(key) for key in group_deps}

    return names


def _parse_pipfile_dependencies(text: str) -> set[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return set()
    names: set[str] = set()
    for section in ("packages", "dev-packages"):
        table = data.get(section)
        if isinstance(table, dict):
            names |= {_normalize(key) for key in table}
    return names


def _json_dependency_names(text: str, keys: tuple[str, ...]) -> frozenset[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    names: set[str] = set()
    for key in keys:
        section = data.get(key)
        if isinstance(section, dict):
            names |= {str(name).lower() for name in section}
    return frozenset(names)
