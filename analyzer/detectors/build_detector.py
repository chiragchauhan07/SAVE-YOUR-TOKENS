"""Build tool / bundler detection.

Containerization tools live in container_detector.py, not here — Docker
builds an image and Docker Compose orchestrates containers, which is a
different question from "what bundles this project's source" (see
docs/DECISIONS.md).
"""

from __future__ import annotations

from analyzer.detectors import manifests, signatures
from analyzer.models import Confidence, Detection, Project


def detect_build_tools(project: Project) -> tuple[Detection, ...]:
    detections = manifests.match_file_signatures(
        project, signatures.BUILD_TOOL_SIGNATURES
    )
    if "vite" in manifests.node_dependencies(project):
        detections.append(Detection("Vite", Confidence.MEDIUM, ("dependency: vite",)))
    return manifests.merge_detections(detections)
