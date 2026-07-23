"""CI/CD provider detection.

GitHub Actions and CircleCI configuration lives in dot-prefixed directories
that the scanner's default walk never enters (D-008), so those two probe the
filesystem directly instead of using the already-scanned file list.
"""

from __future__ import annotations

from analyzer.detectors import manifests, signatures
from analyzer.models import Confidence, Detection, Project


def detect_cicd(project: Project) -> tuple[Detection, ...]:
    detections = manifests.match_file_signatures(
        project, signatures.CICD_FILE_SIGNATURES
    )

    workflow_file = manifests.any_files_matching(
        project, ".github/workflows", (".yml", ".yaml")
    )
    if workflow_file:
        evidence = (workflow_file,)
        detections.append(Detection("GitHub Actions", Confidence.HIGH, evidence))

    gitlab_ci = manifests.path_exists(project, ".gitlab-ci.yml")
    if gitlab_ci:
        detections.append(Detection("GitLab CI", Confidence.HIGH, (gitlab_ci,)))

    circleci_file = manifests.any_files_matching(
        project, ".circleci", (".yml", ".yaml")
    )
    if circleci_file:
        detections.append(Detection("CircleCI", Confidence.HIGH, (circleci_file,)))

    return manifests.merge_detections(detections)
