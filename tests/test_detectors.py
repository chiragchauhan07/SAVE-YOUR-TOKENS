"""Unit tests for the Phase 2 identification detectors."""

from __future__ import annotations

import pytest

from analyzer import Confidence, analyze_repository, scan_repository
from analyzer.detectors import identify_project
from analyzer.detectors.build_detector import detect_build_tools
from analyzer.detectors.cicd_detector import detect_cicd
from analyzer.detectors.container_detector import detect_containers
from analyzer.detectors.environment_detector import detect_environment
from analyzer.detectors.framework_detector import detect_frameworks
from analyzer.detectors.language_detector import detect_languages
from analyzer.detectors.package_manager_detector import detect_package_managers
from analyzer.detectors.repository_classifier import classify_repository


def write_files(root, files: dict[str, str]) -> None:
    """Materialise a fake repository from a ``{relative path: content}`` map."""
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def names(detections) -> set[str]:
    return {detection.name for detection in detections}


# --- language detector -------------------------------------------------


def test_language_stats_ordered_by_size(tmp_path):
    write_files(
        tmp_path,
        {
            "main.py": "x = 1\n" * 100,
            "app.ts": "const x = 1;\n",
            "styles.css": "body {}\n",
        },
    )
    project = scan_repository(tmp_path)
    languages = detect_languages(project)
    assert [lang.name for lang in languages] == ["Python", "TypeScript", "CSS"]
    assert pytest.approx(sum(lang.percentage for lang in languages), abs=0.2) == 100.0


def test_language_stats_empty_repo(tmp_path):
    write_files(tmp_path, {"README.md": "hi\n"})
    project = scan_repository(tmp_path)
    assert detect_languages(project) == ()


def test_multi_language_repo_percentages(tmp_path):
    write_files(tmp_path, {"a.py": "a" * 750, "b.js": "b" * 250})
    project = scan_repository(tmp_path)
    languages = {lang.name: lang for lang in detect_languages(project)}
    assert languages["Python"].percentage == 75.0
    assert languages["JavaScript"].percentage == 25.0


# --- framework detector -------------------------------------------------


def test_fastapi_detected_via_requirements(tmp_path):
    write_files(tmp_path, {"requirements.txt": "fastapi==0.110.0\nuvicorn[standard]\n"})
    project = scan_repository(tmp_path)
    detections = detect_frameworks(project)
    assert names(detections) == {"FastAPI"}
    assert detections[0].confidence is Confidence.HIGH
    assert "dependency: fastapi" in detections[0].evidence


def test_django_via_manage_py_without_manifest_is_medium_confidence(tmp_path):
    write_files(tmp_path, {"manage.py": "#!/usr/bin/env python\n"})
    project = scan_repository(tmp_path)
    detections = detect_frameworks(project)
    assert names(detections) == {"Django"}
    assert detections[0].confidence is Confidence.MEDIUM


def test_django_via_manifest_and_manage_py_is_high_with_both_evidence(tmp_path):
    write_files(
        tmp_path,
        {"manage.py": "#!/usr/bin/env python\n", "requirements.txt": "django==5.0\n"},
    )
    project = scan_repository(tmp_path)
    detections = detect_frameworks(project)
    assert names(detections) == {"Django"}
    django = detections[0]
    assert django.confidence is Confidence.HIGH
    assert len(django.evidence) == 2


def test_react_and_nextjs_via_package_json(tmp_path):
    write_files(
        tmp_path,
        {
            "package.json": (
                '{"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}'
            )
        },
    )
    project = scan_repository(tmp_path)
    detections = detect_frameworks(project)
    assert names(detections) == {"React", "Next.js"}


def test_laravel_via_composer_json(tmp_path):
    write_files(
        tmp_path,
        {"composer.json": '{"require": {"laravel/framework": "^10.0"}}'},
    )
    project = scan_repository(tmp_path)
    assert names(detect_frameworks(project)) == {"Laravel"}


def test_flutter_via_pubspec(tmp_path):
    write_files(
        tmp_path,
        {"pubspec.yaml": "name: demo\ndependencies:\n  flutter:\n    sdk: flutter\n"},
    )
    project = scan_repository(tmp_path)
    assert names(detect_frameworks(project)) == {"Flutter"}


def test_spring_boot_via_pom_xml(tmp_path):
    write_files(
        tmp_path,
        {
            "pom.xml": (
                "<project><dependencies><dependency>"
                "<artifactId>spring-boot-starter-web</artifactId>"
                "</dependency></dependencies></project>"
            )
        },
    )
    project = scan_repository(tmp_path)
    assert names(detect_frameworks(project)) == {"Spring Boot"}


def test_no_false_positive_frameworks_on_plain_repo(tmp_path):
    write_files(tmp_path, {"README.md": "just docs\n"})
    project = scan_repository(tmp_path)
    assert detect_frameworks(project) == ()


def test_conflicting_evidence_no_django_without_any_signal(tmp_path):
    write_files(tmp_path, {"requirements.txt": "flask==3.0\n"})
    project = scan_repository(tmp_path)
    assert names(detect_frameworks(project)) == {"Flask"}


# --- package manager detector -------------------------------------------


def test_poetry_detected_from_pyproject_without_lockfile(tmp_path):
    write_files(tmp_path, {"pyproject.toml": "[tool.poetry]\nname = 'demo'\n"})
    project = scan_repository(tmp_path)
    assert names(detect_package_managers(project)) == {"Poetry"}


def test_uv_detected_from_pyproject(tmp_path):
    write_files(tmp_path, {"pyproject.toml": "[tool.uv]\n"})
    project = scan_repository(tmp_path)
    assert names(detect_package_managers(project)) == {"uv"}


def test_npm_default_fallback_when_only_package_json(tmp_path):
    write_files(tmp_path, {"package.json": "{}"})
    project = scan_repository(tmp_path)
    detections = detect_package_managers(project)
    assert names(detections) == {"npm"}
    assert detections[0].confidence is Confidence.MEDIUM


def test_yarn_lockfile_suppresses_npm_fallback(tmp_path):
    write_files(tmp_path, {"package.json": "{}", "yarn.lock": ""})
    project = scan_repository(tmp_path)
    assert names(detect_package_managers(project)) == {"Yarn"}


def test_no_package_managers_on_empty_repo(tmp_path):
    write_files(tmp_path, {"README.md": "hi\n"})
    project = scan_repository(tmp_path)
    assert detect_package_managers(project) == ()


# --- build detector -------------------------------------------------


def test_docker_detected_via_dockerfile(tmp_path):
    write_files(tmp_path, {"Dockerfile": "FROM python:3.12\n"})
    project = scan_repository(tmp_path)
    assert names(detect_build_tools(project)) == {"Docker"}


def test_vite_via_config_file(tmp_path):
    write_files(tmp_path, {"vite.config.ts": "export default {}\n"})
    project = scan_repository(tmp_path)
    detections = detect_build_tools(project)
    assert names(detections) == {"Vite"}
    assert detections[0].confidence is Confidence.HIGH


def test_vite_via_dependency_only_is_medium_confidence(tmp_path):
    write_files(tmp_path, {"package.json": '{"devDependencies": {"vite": "^5.0.0"}}'})
    project = scan_repository(tmp_path)
    detections = detect_build_tools(project)
    assert names(detections) == {"Vite"}
    assert detections[0].confidence is Confidence.MEDIUM


# --- CI/CD detector -------------------------------------------------


def test_github_actions_detected_despite_hidden_directory(tmp_path):
    write_files(tmp_path, {".github/workflows/ci.yml": "name: CI\n"})
    project = scan_repository(tmp_path)
    # The scanner excludes .github by default (D-008); the CI detector must
    # still find it via a direct filesystem probe.
    assert all(not str(f.path).startswith(".github") for f in project.files)
    assert names(detect_cicd(project)) == {"GitHub Actions"}


def test_gitlab_ci_detected(tmp_path):
    write_files(tmp_path, {".gitlab-ci.yml": "stages: []\n"})
    project = scan_repository(tmp_path)
    assert names(detect_cicd(project)) == {"GitLab CI"}


def test_jenkins_detected(tmp_path):
    write_files(tmp_path, {"Jenkinsfile": "pipeline {}\n"})
    project = scan_repository(tmp_path)
    assert names(detect_cicd(project)) == {"Jenkins"}


def test_no_cicd_on_plain_repo(tmp_path):
    write_files(tmp_path, {"README.md": "hi\n"})
    project = scan_repository(tmp_path)
    assert detect_cicd(project) == ()


# --- container detector -------------------------------------------------


def test_docker_compose_detected(tmp_path):
    write_files(tmp_path, {"docker-compose.yml": "services: {}\n"})
    project = scan_repository(tmp_path)
    assert names(detect_containers(project)) == {"Docker Compose"}


def test_helm_chart_detected(tmp_path):
    write_files(tmp_path, {"charts/demo/Chart.yaml": "name: demo\n"})
    project = scan_repository(tmp_path)
    assert names(detect_containers(project)) == {"Helm"}


def test_kubernetes_manifest_directory_detected(tmp_path):
    write_files(tmp_path, {"k8s/deployment.yaml": "apiVersion: apps/v1\n"})
    project = scan_repository(tmp_path)
    detections = detect_containers(project)
    assert names(detections) == {"Kubernetes"}
    assert detections[0].confidence is Confidence.MEDIUM


# --- environment detector -------------------------------------------------


def test_env_example_detected_despite_being_hidden(tmp_path):
    write_files(tmp_path, {".env.example": "API_KEY=\n"})
    project = scan_repository(tmp_path)
    assert all(not f.name.startswith(".env") for f in project.files)
    assert names(detect_environment(project)) == {".env.example"}


def test_compose_yaml_detected_as_environment_surface(tmp_path):
    write_files(tmp_path, {"compose.yaml": "services: {}\n"})
    project = scan_repository(tmp_path)
    assert names(detect_environment(project)) == {"compose.yaml"}


def test_no_environment_surfaces_on_plain_repo(tmp_path):
    write_files(tmp_path, {"README.md": "hi\n"})
    project = scan_repository(tmp_path)
    assert detect_environment(project) == ()


# --- repository classifier -------------------------------------------------


def test_classify_full_stack_web_application(tmp_path):
    write_files(
        tmp_path,
        {
            "requirements.txt": "fastapi\n",
            "package.json": '{"dependencies": {"react": "^18.0.0"}}',
        },
    )
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Full Stack Web Application"


def test_classify_full_stack_ai_web_application(tmp_path):
    write_files(
        tmp_path,
        {
            "requirements.txt": "fastapi\nopenai\n",
            "package.json": '{"dependencies": {"react": "^18.0.0"}}',
        },
    )
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Full Stack AI Web Application"


def test_classify_rest_api(tmp_path):
    write_files(tmp_path, {"requirements.txt": "fastapi\n"})
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "REST API"


def test_classify_frontend_application(tmp_path):
    write_files(tmp_path, {"package.json": '{"dependencies": {"react": "^18.0.0"}}'})
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Frontend Application"


def test_classify_mobile_app(tmp_path):
    write_files(
        tmp_path,
        {"pubspec.yaml": "name: demo\ndependencies:\n  flutter:\n    sdk: flutter\n"},
    )
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Mobile App"


def test_classify_monorepo_overrides_frameworks(tmp_path):
    write_files(
        tmp_path,
        {
            "turbo.json": "{}",
            "package.json": '{"dependencies": {"react": "^18.0.0"}}',
        },
    )
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Monorepo"


def test_classify_cli_tool(tmp_path):
    pyproject = (
        "[project]\nname = 'demo'\n[project.scripts]\ndemo = 'demo:main'\n"
    )
    write_files(tmp_path, {"pyproject.toml": pyproject})
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "CLI Tool"


def test_classify_python_library(tmp_path):
    pyproject = "[build-system]\nrequires = ['setuptools']\n"
    write_files(tmp_path, {"pyproject.toml": pyproject})
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Python Library"


def test_classify_ai_project(tmp_path):
    write_files(tmp_path, {"requirements.txt": "openai\nanthropic\n"})
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "AI Project"


def test_classify_machine_learning_project(tmp_path):
    write_files(tmp_path, {"requirements.txt": "torch\nscikit-learn\n"})
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Machine Learning Project"


def test_classify_unknown_on_empty_repo(tmp_path):
    project = identify_project(scan_repository(tmp_path))
    assert project.repository_type.name == "Unknown"
    assert project.repository_type.confidence is Confidence.LOW


def test_classify_reachable_via_classify_repository_directly(tmp_path):
    write_files(tmp_path, {"requirements.txt": "flask\n"})
    project = identify_project(scan_repository(tmp_path))
    assert classify_repository(project).name == "REST API"


# --- identify_project / analyze_repository integration -------------------


def test_identify_project_never_throws_on_empty_repo(tmp_path):
    project = identify_project(scan_repository(tmp_path))
    assert project.languages == ()
    assert project.frameworks == ()
    assert project.package_managers == ()
    assert project.build_tools == ()
    assert project.ci_providers == ()
    assert project.container_tools == ()
    assert project.environment_files == ()
    assert project.repository_type is not None


def test_analyze_repository_end_to_end_on_sample_repo():
    project = analyze_repository("sample_repo")
    assert {lang.name for lang in project.languages} == {"Python"}
    assert names(project.frameworks) == {"Flask"}
    assert names(project.package_managers) == {"pip"}
    assert project.repository_type.name == "REST API"


def test_identify_project_preserves_scan_results(tmp_path):
    write_files(tmp_path, {"main.py": "print(1)\n"})
    scanned = scan_repository(tmp_path)
    identified = identify_project(scanned)
    assert identified.files == scanned.files
    assert identified.stats == scanned.stats
