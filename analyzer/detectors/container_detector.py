"""Containerization technology detection.

Docker Compose, Helm and Kustomize are unambiguous file-signature matches.
Raw Kubernetes manifests have no fixed file name, so they're inferred from
the conventional ``k8s/`` or ``kubernetes/`` directory instead — weaker
(MEDIUM) evidence than a named manifest file.
"""

from __future__ import annotations

from analyzer.detectors import manifests, signatures
from analyzer.models import Confidence, Detection, Project

_KUBERNETES_DIRECTORY_NAMES = frozenset({"k8s", "kubernetes"})


def detect_containers(project: Project) -> tuple[Detection, ...]:
    detections = manifests.match_file_signatures(
        project, signatures.CONTAINER_FILE_SIGNATURES
    )
    detections += _detect_kubernetes_directory(project)
    return manifests.merge_detections(detections)


def _detect_kubernetes_directory(project: Project) -> list[Detection]:
    for file in project.files:
        if file.extension not in {".yml", ".yaml"}:
            continue
        if _KUBERNETES_DIRECTORY_NAMES & set(file.path.parts[:-1]):
            return [Detection("Kubernetes", Confidence.MEDIUM, (str(file.path),))]
    return []
