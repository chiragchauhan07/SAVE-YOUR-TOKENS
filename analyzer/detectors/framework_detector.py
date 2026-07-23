"""Application framework detection.

Evidence is layered: a dependency declared in a manifest (requirements.txt,
pyproject.toml, package.json, composer.json) is HIGH confidence; a
recognised conventional file without manifest confirmation (``manage.py``
with Django absent from every manifest) is MEDIUM. A framework with neither
kind of evidence is never reported — nothing here is a guess.

Spring Boot and Flutter aren't manifest-dependency checks (Maven/Gradle and
pubspec.yaml aren't JSON/TOML), so they get a small dedicated substring
check instead of the generic engine.
"""

from __future__ import annotations

from analyzer.detectors import manifests, signatures
from analyzer.models import Confidence, Detection, Project


def detect_frameworks(project: Project) -> tuple[Detection, ...]:
    detections: list[Detection] = []
    detections += manifests.match_dependency_signatures(
        project,
        signatures.PYTHON_FRAMEWORK_SIGNATURES,
        manifests.python_dependencies(project),
    )
    detections += manifests.match_dependency_signatures(
        project,
        signatures.JS_FRAMEWORK_SIGNATURES,
        manifests.node_dependencies(project),
    )
    detections += manifests.match_dependency_signatures(
        project,
        signatures.PHP_FRAMEWORK_SIGNATURES,
        manifests.composer_dependencies(project),
    )
    detections += _detect_spring_boot(project)
    detections += _detect_flutter(project)
    return manifests.merge_detections(detections)


def _detect_spring_boot(project: Project) -> list[Detection]:
    evidence = tuple(
        f"file: {filename}"
        for filename in ("pom.xml", "build.gradle", "build.gradle.kts")
        if (text := manifests.read_text(project, filename)) and "spring-boot" in text
    )
    return [Detection("Spring Boot", Confidence.HIGH, evidence)] if evidence else []


def _detect_flutter(project: Project) -> list[Detection]:
    text = manifests.read_text(project, "pubspec.yaml")
    if text and "sdk: flutter" in text:
        return [Detection("Flutter", Confidence.HIGH, ("file: pubspec.yaml",))]
    return []
