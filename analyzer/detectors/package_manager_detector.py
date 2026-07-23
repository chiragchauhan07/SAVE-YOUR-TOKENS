"""Package manager detection.

Mostly lockfile presence (unambiguous, HIGH confidence). Poetry and uv also
get a pyproject.toml content check, since a project can declare one without
committing its lock file. npm is the deterministic Node default: a
package.json with no other lockfile implies npm, at MEDIUM confidence since
nothing was committed to confirm it.
"""

from __future__ import annotations

from analyzer.detectors import manifests, signatures
from analyzer.models import Confidence, Detection, Project

_NODE_PACKAGE_MANAGERS = frozenset({"npm", "Yarn", "pnpm", "Bun"})


def detect_package_managers(project: Project) -> tuple[Detection, ...]:
    detections = manifests.match_file_signatures(
        project, signatures.PACKAGE_MANAGER_SIGNATURES
    )
    detections += _detect_from_pyproject(project)
    detections += _detect_default_npm(project, detections)
    return manifests.merge_detections(detections)


def _detect_from_pyproject(project: Project) -> list[Detection]:
    text = manifests.read_text(project, "pyproject.toml")
    if not text:
        return []
    detections = []
    if "[tool.poetry]" in text:
        evidence = ("file: pyproject.toml ([tool.poetry])",)
        detections.append(Detection("Poetry", Confidence.HIGH, evidence))
    if "[tool.uv]" in text:
        detections.append(
            Detection("uv", Confidence.HIGH, ("file: pyproject.toml ([tool.uv])",))
        )
    return detections


def _detect_default_npm(project: Project, existing: list[Detection]) -> list[Detection]:
    if any(detection.name in _NODE_PACKAGE_MANAGERS for detection in existing):
        return []
    if project.find("package.json"):
        evidence = ("file: package.json (no lockfile committed)",)
        return [Detection("npm", Confidence.MEDIUM, evidence)]
    return []
