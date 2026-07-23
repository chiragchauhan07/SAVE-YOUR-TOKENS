"""Environment / configuration surface detection.

Identifies *where* configuration lives, never its content. ``.env.example``
and friends are dot-prefixed and excluded from the scanner's default walk
(D-008), so they're probed directly against the filesystem; compose files
are ordinary names already in the scanned file list.
"""

from __future__ import annotations

from analyzer.detectors import manifests, signatures
from analyzer.models import Confidence, Detection, Project


def detect_environment(project: Project) -> tuple[Detection, ...]:
    detections: list[Detection] = []

    for filename in signatures.ENVIRONMENT_FILENAMES:
        found = manifests.path_exists(project, filename)
        if found:
            detections.append(Detection(filename, Confidence.HIGH, (found,)))

    for filename in signatures.COMPOSE_FILENAMES:
        for file in project.find(filename):
            detections.append(Detection(filename, Confidence.HIGH, (str(file.path),)))

    return manifests.merge_detections(detections)
