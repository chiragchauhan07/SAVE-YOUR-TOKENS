"""Static evidence tables for the Phase 2 detectors.

This is the Phase 2 equivalent of ``analyzer/constants.py`` (see D-006):
identification evidence as data, not logic. Supporting a new language,
framework, package manager or tool should mean adding an entry here, never
editing a detector function.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FileSignature:
    """A tool identified purely by the presence of specific file names."""

    name: str
    filenames: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependencySignature:
    """A framework identified by a manifest dependency, or a fallback file.

    A dependency match is HIGH confidence. A ``config_files`` match without
    a dependency match is MEDIUM — the file is a strong convention (e.g.
    ``manage.py``) but nothing declared the framework by name.
    """

    name: str
    dependency_names: tuple[str, ...]
    config_files: tuple[str, ...] = ()


#: Extension -> language name. Deliberately limited to languages and markup
#: with real signal for "what stack is this" — data/config formats such as
#: JSON or YAML are not included.
LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".pyw": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".dart": "Dart",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".html": "HTML",
    ".htm": "HTML",
}

PYTHON_FRAMEWORK_SIGNATURES: tuple[DependencySignature, ...] = (
    DependencySignature("FastAPI", ("fastapi",)),
    DependencySignature("Django", ("django",), config_files=("manage.py",)),
    DependencySignature("Flask", ("flask",)),
    DependencySignature("Streamlit", ("streamlit",)),
    DependencySignature("Litestar", ("litestar",)),
    DependencySignature("Sanic", ("sanic",)),
)

JS_FRAMEWORK_SIGNATURES: tuple[DependencySignature, ...] = (
    DependencySignature(
        "Next.js",
        ("next",),
        config_files=("next.config.js", "next.config.ts", "next.config.mjs"),
    ),
    DependencySignature(
        "Nuxt", ("nuxt",), config_files=("nuxt.config.js", "nuxt.config.ts")
    ),
    DependencySignature("React", ("react",)),
    DependencySignature("Vue", ("vue",)),
    DependencySignature("Angular", ("@angular/core",), config_files=("angular.json",)),
    DependencySignature("Svelte", ("svelte",)),
    DependencySignature("Express", ("express",)),
    DependencySignature("NestJS", ("@nestjs/core",)),
)

PHP_FRAMEWORK_SIGNATURES: tuple[DependencySignature, ...] = (
    DependencySignature("Laravel", ("laravel/framework",)),
)

PACKAGE_MANAGER_SIGNATURES: tuple[FileSignature, ...] = (
    FileSignature("Poetry", ("poetry.lock",)),
    FileSignature("uv", ("uv.lock",)),
    FileSignature("Pipenv", ("Pipfile",)),
    FileSignature("pip", ("requirements.txt",)),
    FileSignature("pnpm", ("pnpm-lock.yaml",)),
    FileSignature("Yarn", ("yarn.lock",)),
    FileSignature("Bun", ("bun.lockb", "bun.lock")),
    FileSignature("npm", ("package-lock.json",)),
    FileSignature("Maven", ("pom.xml",)),
    FileSignature("Gradle", ("build.gradle", "build.gradle.kts")),
    FileSignature("Cargo", ("Cargo.toml",)),
    FileSignature("Go Modules", ("go.mod",)),
)

BUILD_TOOL_SIGNATURES: tuple[FileSignature, ...] = (
    FileSignature("Docker", ("Dockerfile",)),
    FileSignature("Turborepo", ("turbo.json",)),
    FileSignature("Nx", ("nx.json",)),
    FileSignature("Webpack", ("webpack.config.js", "webpack.config.ts")),
    FileSignature("Rollup", ("rollup.config.js", "rollup.config.ts")),
    FileSignature("Vite", ("vite.config.js", "vite.config.ts")),
)

CICD_FILE_SIGNATURES: tuple[FileSignature, ...] = (
    FileSignature("Jenkins", ("Jenkinsfile",)),
    FileSignature("Azure Pipelines", ("azure-pipelines.yml", "azure-pipelines.yaml")),
)

CONTAINER_FILE_SIGNATURES: tuple[FileSignature, ...] = (
    FileSignature(
        "Docker Compose",
        ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"),
    ),
    FileSignature("Helm", ("Chart.yaml",)),
    FileSignature("Kubernetes", ("kustomization.yaml", "kustomization.yml")),
)

#: Dot-prefixed, so excluded from the scanner's default walk (D-008).
#: Detectors probe for these directly against the filesystem.
ENVIRONMENT_FILENAMES: tuple[str, ...] = (
    ".env.example",
    ".env.template",
    ".env.sample",
)

#: Compose files are both a containerization technology (container_detector)
#: and a configuration surface (environment_detector) — two different
#: questions about the same file, so it is listed in both places.
COMPOSE_FILENAMES: tuple[str, ...] = (
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
)

MONOREPO_MARKER_FILES: tuple[str, ...] = (
    "pnpm-workspace.yaml",
    "turbo.json",
    "nx.json",
    "lerna.json",
)

BACKEND_FRAMEWORK_NAMES: frozenset[str] = frozenset(
    {
        "FastAPI",
        "Django",
        "Flask",
        "Litestar",
        "Sanic",
        "Express",
        "NestJS",
        "Spring Boot",
        "Laravel",
    }
)
FRONTEND_FRAMEWORK_NAMES: frozenset[str] = frozenset(
    {"React", "Vue", "Angular", "Svelte"}
)
#: Meta-frameworks that commonly serve both roles in the same project.
FULLSTACK_META_FRAMEWORK_NAMES: frozenset[str] = frozenset({"Next.js", "Nuxt"})

#: LLM/agent-tooling dependencies — drive the "AI Project" classification,
#: distinct from classical ML training libraries below.
AI_DEPENDENCY_MARKERS: frozenset[str] = frozenset(
    {"openai", "anthropic", "langchain", "langchain-core", "llama-index"}
)
#: Classical/deep-learning libraries — drive "Machine Learning Project".
ML_DEPENDENCY_MARKERS: frozenset[str] = frozenset(
    {
        "torch",
        "tensorflow",
        "keras",
        "scikit-learn",
        "xgboost",
        "lightgbm",
        "transformers",
    }
)
