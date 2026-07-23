"""Phase 2: identify what a scanned repository actually is.

Each module in this package answers one narrow question about a Project —
languages, frameworks, package managers, build tools, CI/CD, containers,
environment surfaces, or overall repository type — from deterministic
evidence only: manifests, lockfiles, conventional file names. No detector
reads application source code, inspects function bodies, or calls a
language model. Unknown is always a valid result.

``identify_project()`` is the single entry point: it runs every detector and
returns a new ``Project`` with the results attached. The scanner (Phase 1)
is untouched by any of this — detection is a separate step over its output.
"""

from __future__ import annotations

from dataclasses import replace

from analyzer.detectors.build_detector import detect_build_tools
from analyzer.detectors.cicd_detector import detect_cicd
from analyzer.detectors.container_detector import detect_containers
from analyzer.detectors.environment_detector import detect_environment
from analyzer.detectors.framework_detector import detect_frameworks
from analyzer.detectors.language_detector import detect_languages
from analyzer.detectors.package_manager_detector import detect_package_managers
from analyzer.detectors.repository_classifier import classify_repository
from analyzer.models import Project

__all__ = ["identify_project"]


def identify_project(project: Project) -> Project:
    """Run every Phase 2 detector and return an identified Project.

    Classification runs last because it reasons about the frameworks
    already attached to the project.
    """
    identified = replace(
        project,
        languages=detect_languages(project),
        frameworks=detect_frameworks(project),
        package_managers=detect_package_managers(project),
        build_tools=detect_build_tools(project),
        ci_providers=detect_cicd(project),
        container_tools=detect_containers(project),
        environment_files=detect_environment(project),
    )
    return replace(identified, repository_type=classify_repository(identified))
