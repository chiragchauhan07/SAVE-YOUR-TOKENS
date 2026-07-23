"""Unit tests for the Phase 6 top-level incremental orchestration package."""

from __future__ import annotations

from analyzer import analyze_repository
from analyzer.caching import CacheStatus, cache_path
from generator import write_knowledge_base
from incremental import (
    clear_cache,
    inspect_cache,
    preview_changes,
    update_knowledge_base,
)

_EXPECTED_KB_FILES = {
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

_FLASK_APP = (
    "from flask import Flask\n"
    "app = Flask(__name__)\n\n"
    "@app.route('/health')\n"
    "def health():\n    return 'ok'\n"
)

_USER_MODEL = (
    "from pydantic import BaseModel\n\n\nclass User(BaseModel):\n    id: int\n"
)
_ORDER_MODEL = (
    "from pydantic import BaseModel\n\n\nclass Order(BaseModel):\n    id: int\n"
)


def write_files(root, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# --- update_knowledge_base: first run / no-change fast path -----------------


def test_first_update_writes_every_document(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    report = update_knowledge_base(tmp_path)

    assert report.cache_status is CacheStatus.MISSING
    assert set(report.documents_regenerated) == _EXPECTED_KB_FILES
    assert report.documents_unchanged == ()
    assert report.forced_full_analysis is True
    output_dir = tmp_path / ".blueprint"
    assert output_dir.is_dir()
    for filename in _EXPECTED_KB_FILES:
        assert (output_dir / filename).is_file()


def test_second_update_with_no_changes_writes_nothing(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    update_knowledge_base(tmp_path)

    report = update_knowledge_base(tmp_path)

    assert report.cache_status is CacheStatus.VALID
    assert report.documents_regenerated == ()
    assert set(report.documents_unchanged) == _EXPECTED_KB_FILES
    assert report.forced_full_analysis is False
    assert report.files_analyzed == 0


# --- selective generation -------------------------------------------------


def test_selective_generation_only_rewrites_affected_documents(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "auth.py": "SECRET = 1\n"})
    update_knowledge_base(tmp_path)

    (tmp_path / "app.py").write_text(
        _FLASK_APP + "\n@app.route('/new')\ndef new():\n    return ''\n"
    )
    report = update_knowledge_base(tmp_path)

    assert "API_ROUTES.md" in report.documents_regenerated
    assert "DATABASE.md" in report.documents_unchanged
    assert "AUTHENTICATION.md" in report.documents_unchanged
    assert report.new_routes == ("GET /new",)


def test_unrelated_change_does_not_touch_unrelated_documents(tmp_path):
    write_files(
        tmp_path,
        {
            "app.py": _FLASK_APP,
            "models.py": _USER_MODEL,
        },
    )
    update_knowledge_base(tmp_path)

    # Adding a brand-new, unrelated module shouldn't touch DATABASE.md's
    # content (models.py's own model is unchanged) even though MODULES.md
    # must regenerate (a new module now exists).
    write_files(tmp_path, {"unrelated.py": "PI = 3.14\n"})
    report = update_knowledge_base(tmp_path)

    assert "MODULES.md" in report.documents_regenerated
    assert "DATABASE.md" in report.documents_unchanged


# --- force / determinism -------------------------------------------------


def test_force_matches_incremental_result(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    update_knowledge_base(tmp_path)
    (tmp_path / "app.py").write_text(
        _FLASK_APP + "\n@app.route('/x')\ndef x():\n    return ''\n"
    )
    update_knowledge_base(tmp_path)  # settle into incremental state

    output_dir = tmp_path / ".blueprint"
    before = {f.name: f.read_bytes() for f in output_dir.glob("*.md")}

    report = update_knowledge_base(tmp_path, force=True)

    after = {f.name: f.read_bytes() for f in output_dir.glob("*.md")}
    assert before == after
    assert report.forced_full_analysis is True


def test_update_matches_cli_generate_byte_for_byte(tmp_path):
    # The output directories must sit outside the scanned repo — writing
    # into a custom (non-`.blueprint`) directory *inside* the repo would
    # make the second scan see the first run's own output files.
    repo_root = tmp_path / "repo"
    write_files(repo_root, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    update_knowledge_base(repo_root, output_dir=tmp_path / "via_update")

    project = analyze_repository(repo_root)
    write_knowledge_base(project, tmp_path / "via_generate")

    for filename in _EXPECTED_KB_FILES:
        incremental_bytes = (tmp_path / "via_update" / filename).read_bytes()
        full_bytes = (tmp_path / "via_generate" / filename).read_bytes()
        assert incremental_bytes == full_bytes


# --- change report content -------------------------------------------------


def test_change_report_tracks_new_and_removed_routes(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    update_knowledge_base(tmp_path)

    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n")
    report = update_knowledge_base(tmp_path)

    assert report.removed_routes == ("GET /health",)
    assert report.new_routes == ()


def test_change_report_tracks_new_and_removed_models(tmp_path):
    write_files(
        tmp_path,
        {"models.py": _USER_MODEL},
    )
    update_knowledge_base(tmp_path)

    write_files(
        tmp_path,
        {"models.py": _ORDER_MODEL},
    )
    report = update_knowledge_base(tmp_path)

    assert report.new_models == ("Order",)
    assert report.removed_models == ("User",)


def test_change_report_changed_categories(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    update_knowledge_base(tmp_path)

    (tmp_path / "app.py").write_text(
        _FLASK_APP + "\n@app.route('/new')\ndef new():\n    return ''\n"
    )
    report = update_knowledge_base(tmp_path)

    assert "routes" in report.changed_categories
    assert "authentication" not in report.changed_categories


def test_change_report_first_run_marks_every_category_changed(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    report = update_knowledge_base(tmp_path)
    assert "routes" in report.changed_categories
    assert "modules" in report.changed_categories


# --- output_dir override -------------------------------------------------


def test_update_respects_custom_output_dir(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    custom = tmp_path / "custom-kb"
    update_knowledge_base(tmp_path, output_dir=custom)
    assert (custom / "OVERVIEW.md").is_file()
    assert not (tmp_path / ".blueprint").exists()


# --- cache inspection / clearing -------------------------------------------------


def test_inspect_cache_missing(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    info = inspect_cache(tmp_path)
    assert info.exists is False
    assert info.valid is False
    assert info.status is CacheStatus.MISSING


def test_inspect_cache_valid_after_update(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    update_knowledge_base(tmp_path)

    info = inspect_cache(tmp_path)
    assert info.exists is True
    assert info.valid is True
    assert info.status is CacheStatus.VALID
    assert info.tracked_files == 2


def test_clear_cache_removes_file(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    update_knowledge_base(tmp_path)
    assert cache_path(tmp_path / ".blueprint").is_file()

    removed = clear_cache(tmp_path)
    assert removed is True
    assert not cache_path(tmp_path / ".blueprint").exists()


def test_clear_cache_when_nothing_to_clear(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    assert clear_cache(tmp_path) is False


def test_update_after_cache_clear_is_a_full_run(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    update_knowledge_base(tmp_path)
    clear_cache(tmp_path)

    report = update_knowledge_base(tmp_path)
    assert report.cache_status is CacheStatus.MISSING
    assert report.forced_full_analysis is True


# --- preview_changes: read-only -------------------------------------------------


def test_preview_changes_does_not_write_cache_or_knowledge_base(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    preview = preview_changes(tmp_path)

    assert preview.cache_status is CacheStatus.MISSING
    assert len(preview.change_set.new_files) == 1
    assert not cache_path(tmp_path / ".blueprint").exists()
    assert not (tmp_path / ".blueprint").exists()


def test_preview_changes_reflects_pending_modifications(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    update_knowledge_base(tmp_path)

    (tmp_path / "app.py").write_text(_FLASK_APP + "\nX = 1\n")
    preview = preview_changes(tmp_path)

    assert preview.cache_status is CacheStatus.VALID
    assert [str(p) for p in preview.change_set.modified_files] == ["app.py"]

    # Calling preview again afterward must not have changed anything either.
    preview_again = preview_changes(tmp_path)
    assert preview_again.change_set.modified_files == preview.change_set.modified_files
