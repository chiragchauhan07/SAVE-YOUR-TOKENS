"""Unit tests for the Phase 4 Knowledge Base generator."""

from __future__ import annotations

import dataclasses
from pathlib import Path, PurePosixPath

import pytest

from analyzer import analyze_repository
from analyzer.models import (
    Confidence,
    DatabaseModel,
    Detection,
    EntryPoint,
    FileInfo,
    ImportantFile,
    ImportEdge,
    LanguageStat,
    ModuleDependency,
    ModuleInfo,
    Project,
    RepositoryStats,
    Route,
)
from generator import generate_knowledge_base, write_knowledge_base
from generator.navigation import RELATED_DOCUMENTS
from generator.renderers import (
    ai_context,
    architecture,
    authentication,
    configuration,
    database,
    dependencies,
    important_files,
    index,
    modules,
    overview,
    project_structure,
    routes,
)

_EXPECTED_FILES = {
    "OVERVIEW.md",
    "PROJECT_STRUCTURE.md",
    "ARCHITECTURE.md",
    "MODULES.md",
    "DEPENDENCIES.md",
    "API_ROUTES.md",
    "DATABASE.md",
    "AUTHENTICATION.md",
    "CONFIGURATION.md",
    "IMPORTANT_FILES.md",
    "AI_CONTEXT.md",
    "INDEX.md",
}


def make_project(**overrides: object) -> Project:
    """A minimal, empty Project — override only the fields a test needs."""
    stats = RepositoryStats(
        total_files=0,
        total_directories=0,
        total_size_bytes=0,
        files_by_extension={},
        largest_files=(),
    )
    base = Project(root=Path("/repo"), name="repo", files=(), stats=stats)
    return dataclasses.replace(base, **overrides)  # type: ignore[arg-type]


# --- knowledge base structure -------------------------------------------------


def test_generates_exactly_the_expected_files():
    project = make_project()
    documents = generate_knowledge_base(project)
    assert set(documents.keys()) == _EXPECTED_FILES


def test_deterministic_across_repeated_runs():
    project = make_project(
        languages=(LanguageStat("Python", 3, 900, 100.0),),
        entry_points=(
            EntryPoint(
                PurePosixPath("main.py"), "script", None, Confidence.HIGH, ("guard",)
            ),
        ),
    )
    first = generate_knowledge_base(project)
    second = generate_knowledge_base(project)
    assert first == second


def test_every_document_has_related_context_section():
    project = make_project()
    documents = generate_knowledge_base(project)
    for filename, content in documents.items():
        assert "## Related Context" in content, filename


def test_related_context_links_are_valid():
    for source, targets in RELATED_DOCUMENTS.items():
        assert source in _EXPECTED_FILES, f"{source} is not a generated file"
        for target in targets:
            assert target in _EXPECTED_FILES, f"{source} links to unknown file {target}"


def test_no_document_links_to_itself():
    for source, targets in RELATED_DOCUMENTS.items():
        assert source not in targets


# --- empty / partial repositories -------------------------------------------------


def test_empty_repository_generates_graceful_output():
    project = make_project()
    documents = generate_knowledge_base(project)
    assert "No frameworks detected." in documents["OVERVIEW.md"]
    assert "No entry points detected." in documents["ARCHITECTURE.md"]
    assert "No Python modules analysed." in documents["MODULES.md"]
    assert "No internal module dependencies detected." in documents["DEPENDENCIES.md"]
    assert "No circular imports detected." in documents["DEPENDENCIES.md"]
    assert "No API routes detected." in documents["API_ROUTES.md"]
    assert "No database models detected." in documents["DATABASE.md"]
    assert "No authentication mechanisms detected." in documents["AUTHENTICATION.md"]
    assert "No configuration surfaces detected." in documents["CONFIGURATION.md"]
    assert "No files received a ranking signal." in documents["IMPORTANT_FILES.md"]


def test_repository_without_routes_is_graceful():
    project = make_project(
        database_models=(
            DatabaseModel("User", "Pydantic", None, PurePosixPath("m.py"), (), ()),
        )
    )
    documents = generate_knowledge_base(project)
    assert "No API routes detected." in documents["API_ROUTES.md"]
    assert "User" in documents["DATABASE.md"]


def test_repository_without_database_is_graceful():
    project = make_project(
        routes=(Route("GET", "/x", "handler", PurePosixPath("a.py"), "Flask"),)
    )
    documents = generate_knowledge_base(project)
    assert "No database models detected." in documents["DATABASE.md"]
    assert "/x" in documents["API_ROUTES.md"]


def test_repository_without_authentication_is_graceful():
    project = make_project(
        configuration=(
            Detection("Settings Module", Confidence.HIGH, ("file: settings.py",)),
        )
    )
    documents = generate_knowledge_base(project)
    assert "No authentication mechanisms detected." in documents["AUTHENTICATION.md"]
    assert "Settings Module" in documents["CONFIGURATION.md"]


# --- individual renderers -------------------------------------------------


def test_overview_renderer_content():
    project = make_project(
        repository_type=Detection("REST API", Confidence.HIGH, ("framework: Flask",)),
        languages=(LanguageStat("Python", 5, 1000, 100.0),),
        frameworks=(Detection("Flask", Confidence.HIGH, ("dependency: flask",)),),
    )
    document = overview.render(project)
    assert document.filename == "OVERVIEW.md"
    assert "REST API" in document.body
    assert "Python" in document.body
    assert "Flask" in document.body


def test_project_structure_renderer_content():
    stats = RepositoryStats(
        total_files=2,
        total_directories=1,
        total_size_bytes=2048,
        files_by_extension={".py": 2},
        largest_files=(FileInfo(PurePosixPath("big.py"), 2048, ".py"),),
    )
    project = make_project(stats=stats)
    document = project_structure.render(project)
    assert "2" in document.body
    assert "big.py" in document.body
    assert "2.0 KB" in document.body


def test_architecture_renderer_shows_top_ten_and_pointer():
    important = tuple(
        ImportantFile(PurePosixPath(f"f{i}.py"), 10 - i, ("signal",)) for i in range(12)
    )
    project = make_project(important_files=important)
    document = architecture.render(project)
    assert "f0.py" in document.body
    assert "f9.py" in document.body
    assert "f11.py" not in document.body
    assert "See IMPORTANT_FILES.md for the full ranking." in document.body


def test_modules_renderer_lists_names_not_just_counts():
    module = ModuleInfo(
        PurePosixPath("a.py"),
        classes=("Widget",),
        functions=("build",),
        async_functions=("fetch",),
        constants=("MAX",),
        exports=("Widget", "build"),
    )
    project = make_project(modules=(module,))
    document = modules.render(project)
    assert "Widget" in document.body
    assert "build" in document.body
    assert "fetch" in document.body
    assert "MAX" in document.body


def test_dependencies_renderer_formats_cycle():
    project = make_project(circular_imports=(("a.py", "b.py"),))
    document = dependencies.render(project)
    assert "a.py" in document.body
    assert "→" in document.body


def test_dependencies_renderer_counts_external_packages():
    edges = (
        ImportEdge(PurePosixPath("a.py"), "os", False, None),
        ImportEdge(PurePosixPath("a.py"), "os.path", False, None),
        ImportEdge(PurePosixPath("b.py"), "json", False, None),
    )
    project = make_project(imports=edges)
    document = dependencies.render(project)
    assert "os" in document.body
    assert "json" in document.body


def test_dependencies_renderer_ignores_unresolved_relative_imports():
    edges = (ImportEdge(PurePosixPath("mod.py"), "..thing", False, None),)
    project = make_project(imports=edges)
    document = dependencies.render(project)
    assert "No external imports detected." in document.body


def test_routes_renderer_content():
    project = make_project(
        routes=(Route("POST", "/login", "login", PurePosixPath("auth.py"), "FastAPI"),)
    )
    document = routes.render(project)
    assert "POST" in document.body
    assert "/login" in document.body
    assert "FastAPI" in document.body


def test_database_renderer_content():
    model = DatabaseModel(
        "User", "SQLAlchemy", "users", PurePosixPath("m.py"), ("id", "name"), ()
    )
    project = make_project(database_models=(model,))
    document = database.render(project)
    assert "User" in document.body
    assert "users" in document.body
    assert "id" in document.body


def test_authentication_renderer_content():
    project = make_project(
        authentication=(Detection("JWT", Confidence.HIGH, ("import: jwt",)),)
    )
    document = authentication.render(project)
    assert "JWT" in document.body
    assert "import: jwt" in document.body


def test_configuration_renderer_mentions_overview():
    project = make_project()
    document = configuration.render(project)
    assert "OVERVIEW.md" in document.body


def test_important_files_renderer_full_list():
    important = tuple(
        ImportantFile(PurePosixPath(f"f{i}.py"), i, ()) for i in range(15)
    )
    project = make_project(important_files=important)
    document = important_files.render(project)
    assert "f0.py" in document.body
    assert "f14.py" in document.body


def test_ai_context_reading_order_is_conditional():
    project_without_routes = make_project()
    docs = [
        overview.render(project_without_routes),
        architecture.render(project_without_routes),
        routes.render(project_without_routes),
        database.render(project_without_routes),
        authentication.render(project_without_routes),
        configuration.render(project_without_routes),
        modules.render(project_without_routes),
        dependencies.render(project_without_routes),
    ]
    document = ai_context.render(project_without_routes, tuple(docs))
    assert "API_ROUTES.md" not in document.body

    project_with_routes = make_project(
        routes=(Route("GET", "/x", "h", PurePosixPath("a.py"), "Flask"),)
    )
    docs_with_routes = [
        overview.render(project_with_routes),
        architecture.render(project_with_routes),
        routes.render(project_with_routes),
        database.render(project_with_routes),
        authentication.render(project_with_routes),
        configuration.render(project_with_routes),
        modules.render(project_with_routes),
        dependencies.render(project_with_routes),
    ]
    document_with_routes = ai_context.render(
        project_with_routes, tuple(docs_with_routes)
    )
    assert "API_ROUTES.md" in document_with_routes.body


def test_ai_context_lists_excluded_directories():
    project = make_project()
    docs = [
        overview.render(project),
        architecture.render(project),
        modules.render(project),
        dependencies.render(project),
    ]
    document = ai_context.render(project, tuple(docs))
    assert "node_modules" in document.body
    assert "__pycache__" in document.body


def test_index_renderer_links_every_document():
    documents = generate_knowledge_base(make_project())
    from generator.models import Document

    doc_objects = tuple(
        Document(name, name, "desc", "")
        for name in sorted(documents)
        if name != "INDEX.md"
    )
    document = index.render(doc_objects)
    for other in doc_objects:
        assert other.filename in document.body


# --- writer -------------------------------------------------


def test_write_knowledge_base_creates_directory_and_files(tmp_path):
    output_dir = tmp_path / "nested" / ".blueprint"
    project = make_project()
    written = write_knowledge_base(project, output_dir)
    assert len(written) == len(_EXPECTED_FILES)
    assert output_dir.is_dir()
    for path in written:
        assert path.exists()
        assert path.name in _EXPECTED_FILES


def test_written_files_use_lf_line_endings(tmp_path):
    project = make_project()
    written = write_knowledge_base(project, tmp_path)
    for path in written:
        raw = path.read_bytes()
        assert b"\r" not in raw


def test_written_files_contain_no_trailing_carriage_return_after_repeated_write(
    tmp_path,
):
    project = make_project()
    write_knowledge_base(project, tmp_path)
    write_knowledge_base(project, tmp_path)
    for path in tmp_path.glob("*.md"):
        assert b"\r" not in path.read_bytes()


# --- markdown helpers -------------------------------------------------


def test_markdown_table_escapes_pipe_characters():
    from generator import markdown

    result = markdown.table(["A"], [["value | with pipe"]])
    assert "value \\| with pipe" in result


def test_markdown_table_empty_rows_returns_empty_string():
    from generator import markdown

    assert markdown.table(["A"], []) == ""


# --- integration -------------------------------------------------


def test_full_pipeline_on_sample_repo():
    project = analyze_repository("sample_repo")
    documents = generate_knowledge_base(project)
    assert set(documents.keys()) == _EXPECTED_FILES
    assert "Flask" in documents["OVERVIEW.md"]
    assert "/health" in documents["API_ROUTES.md"]


def test_large_synthetic_repository_does_not_crash():
    modules_tuple = tuple(
        ModuleInfo(
            PurePosixPath(f"pkg/mod_{i}.py"),
            classes=(f"Class{i}",),
            functions=(f"func_{i}",),
            async_functions=(),
            constants=(),
            exports=(f"Class{i}", f"func_{i}"),
        )
        for i in range(200)
    )
    dependencies_tuple = tuple(
        ModuleDependency(
            PurePosixPath(f"pkg/mod_{i}.py"), PurePosixPath("pkg/mod_0.py")
        )
        for i in range(1, 200)
    )
    important = tuple(
        ImportantFile(PurePosixPath(f"pkg/mod_{i}.py"), 200 - i, ("imported",))
        for i in range(200)
    )
    project = make_project(
        modules=modules_tuple,
        module_dependencies=dependencies_tuple,
        important_files=important,
    )
    documents = generate_knowledge_base(project)
    assert set(documents.keys()) == _EXPECTED_FILES
    assert "mod_199" in documents["MODULES.md"]


@pytest.mark.parametrize("filename", sorted(_EXPECTED_FILES))
def test_every_document_has_a_top_level_heading(filename):
    documents = generate_knowledge_base(make_project())
    assert documents[filename].startswith("# ")
