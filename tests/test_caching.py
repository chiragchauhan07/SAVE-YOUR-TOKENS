"""Unit tests for the Phase 6 incremental caching engine (analyzer.caching)."""

from __future__ import annotations

import json

from analyzer import analyze_repository, identify_project, scan_repository
from analyzer.caching import CacheStatus, cache_path, reanalyze
from analyzer.caching.cache_io import load_cache, save_cache


def write_files(root, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


_FLASK_APP = (
    "from flask import Flask\n"
    "app = Flask(__name__)\n\n"
    "@app.route('/health')\n"
    "def health():\n    return 'ok'\n"
)


def _project(root):
    return identify_project(scan_repository(root))


def _all_fields_equal(a, b) -> bool:
    fields = (
        "entry_points",
        "modules",
        "imports",
        "circular_imports",
        "routes",
        "database_models",
        "authentication",
        "configuration",
        "module_dependencies",
        "important_files",
    )
    return all(getattr(a, field) == getattr(b, field) for field in fields)


# --- first run / no-change fast path -------------------------------------------------


def test_first_run_no_cache(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert status is CacheStatus.MISSING
    assert previous is None
    assert len(change_set.new_files) == 1
    assert not change_set.modified_files
    assert len(updated.routes) == 1
    assert cache_file.is_file()


def test_second_run_no_changes_reuses_cache_verbatim(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    first, _, _, _ = reanalyze(_project(tmp_path), cache_file)

    second, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert status is CacheStatus.VALID
    assert not change_set.has_changes
    assert _all_fields_equal(first, second)


def test_incremental_matches_full_analysis_after_no_changes(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)
    incremental, *_ = reanalyze(_project(tmp_path), cache_file)

    full = analyze_repository(tmp_path)
    assert _all_fields_equal(incremental, full)


# --- single / multiple file modification ------------------------------------


def test_single_file_modified_only_reparses_that_file(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    (tmp_path / "app.py").write_text(
        _FLASK_APP + "\n@app.route('/new')\ndef new():\n    return ''\n"
    )
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert status is CacheStatus.VALID
    assert [str(p) for p in change_set.modified_files] == ["app.py"]
    assert change_set.files_to_reparse == frozenset({"app.py"})
    assert len(updated.routes) == 2
    # models.py's ModuleInfo survived from cache without reparsing.
    assert any(str(m.file) == "models.py" for m in updated.modules)


def test_multiple_files_modified(tmp_path):
    write_files(tmp_path, {"a.py": "X = 1\n", "b.py": "Y = 2\n", "c.py": "Z = 3\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    (tmp_path / "a.py").write_text("X = 10\n")
    (tmp_path / "b.py").write_text("Y = 20\n")
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert {str(p) for p in change_set.modified_files} == {"a.py", "b.py"}
    assert {str(m.file) for m in updated.modules} == {"a.py", "b.py", "c.py"}
    full = analyze_repository(tmp_path)
    assert _all_fields_equal(updated, full)


def test_touched_but_unchanged_content_is_not_modified(tmp_path):
    """mtime changes but content doesn't (e.g. a checkout) must not count."""
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    path = tmp_path / "app.py"
    path.write_text(path.read_text())  # rewrite identical content -> new mtime
    _, change_set, _, _ = reanalyze(_project(tmp_path), cache_file)

    assert not change_set.modified_files
    assert change_set.unchanged_count == 1


# --- deletions and additions -------------------------------------------------


def test_deleted_file_dropped_from_results(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    (tmp_path / "models.py").unlink()
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert [str(p) for p in change_set.deleted_files] == ["models.py"]
    assert {str(m.file) for m in updated.modules} == {"app.py"}
    full = analyze_repository(tmp_path)
    assert _all_fields_equal(updated, full)


def test_new_file_added(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    write_files(tmp_path, {"extra.py": "CONST = 1\n"})
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert [str(p) for p in change_set.new_files] == ["extra.py"]
    assert {str(m.file) for m in updated.modules} == {"app.py", "extra.py"}


# --- renames -------------------------------------------------


def test_renamed_file_content_identical_is_detected_as_rename(tmp_path):
    write_files(tmp_path, {"models.py": "CONST = 1\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    (tmp_path / "models.py").rename(tmp_path / "data_models.py")
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert len(change_set.renamed_files) == 1
    renamed = change_set.renamed_files[0]
    assert str(renamed.old_path) == "models.py"
    assert str(renamed.new_path) == "data_models.py"
    assert not change_set.new_files
    assert not change_set.deleted_files
    assert [str(m.file) for m in updated.modules] == ["data_models.py"]
    full = analyze_repository(tmp_path)
    assert _all_fields_equal(updated, full)


def test_rename_with_content_change_is_delete_plus_new_not_a_rename(tmp_path):
    write_files(tmp_path, {"models.py": "CONST = 1\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    (tmp_path / "models.py").unlink()
    write_files(tmp_path, {"data_models.py": "CONST = 2\n"})  # different content
    _, change_set, _, _ = reanalyze(_project(tmp_path), cache_file)

    assert not change_set.renamed_files
    assert [str(p) for p in change_set.deleted_files] == ["models.py"]
    assert [str(p) for p in change_set.new_files] == ["data_models.py"]


# --- force -------------------------------------------------


def test_force_ignores_cache_and_matches_full_analysis(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    updated, change_set, status, previous = reanalyze(
        _project(tmp_path), cache_file, force=True
    )

    assert previous is None
    assert len(change_set.new_files) == 2  # everything treated as new
    full = analyze_repository(tmp_path)
    assert _all_fields_equal(updated, full)


# --- cache invalidation -------------------------------------------------


def test_cache_corruption_falls_back_to_full_analysis(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{not valid json", encoding="utf-8")

    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert status is CacheStatus.CORRUPTED
    assert previous is None
    assert len(updated.routes) == 1


def test_cache_missing_required_keys_is_corrupted(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"cache_version": 1}), encoding="utf-8")

    cache, status = load_cache(cache_file, str(tmp_path))
    # cache_version alone matches, but tool_version is absent -> mismatch,
    # not a KeyError explosion.
    assert cache is None
    assert status in (CacheStatus.TOOL_VERSION_MISMATCH, CacheStatus.CORRUPTED)


def test_cache_version_mismatch_falls_back(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    raw["cache_version"] = 999
    cache_file.write_text(json.dumps(raw), encoding="utf-8")

    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)
    assert status is CacheStatus.VERSION_MISMATCH
    assert previous is None
    full = analyze_repository(tmp_path)
    assert _all_fields_equal(updated, full)


def test_tool_version_mismatch_falls_back(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    raw["tool_version"] = "0.0.0-nonexistent"
    cache_file.write_text(json.dumps(raw), encoding="utf-8")

    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)
    assert status is CacheStatus.TOOL_VERSION_MISMATCH
    assert previous is None


def test_cache_missing_file_reports_missing_status(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    cache, status = load_cache(cache_file, str(tmp_path))
    assert cache is None
    assert status is CacheStatus.MISSING


# --- regression: manage.py not duplicated across merge ---------------------


def test_django_manage_entry_point_not_duplicated_across_incremental_runs(tmp_path):
    write_files(
        tmp_path,
        {"manage.py": "#!/usr/bin/env python\n", "app_config.py": "X = 1\n"},
    )
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    (tmp_path / "app_config.py").write_text("X = 2\n")
    updated, *_ = reanalyze(_project(tmp_path), cache_file)

    manage_entries = [ep for ep in updated.entry_points if ep.kind == "django_manage"]
    assert len(manage_entries) == 1


# --- empty / nested repositories -------------------------------------------------


def test_empty_repository(tmp_path):
    cache_file = cache_path(tmp_path / ".ai-context")
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)
    assert updated.modules == ()
    assert not change_set.has_changes  # no files exist to be "new"
    assert status is CacheStatus.MISSING


def test_nested_packages(tmp_path):
    write_files(
        tmp_path,
        {
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "",
            "pkg/sub/mod.py": "from . import sibling\n",
            "pkg/sub/sibling.py": "Y = 1\n",
        },
    )
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    (tmp_path / "pkg/sub/sibling.py").write_text("Y = 2\n")
    updated, change_set, status, previous = reanalyze(_project(tmp_path), cache_file)

    assert [str(p) for p in change_set.modified_files] == ["pkg/sub/sibling.py"]
    full = analyze_repository(tmp_path)
    assert _all_fields_equal(updated, full)


# --- hashing fast path -------------------------------------------------


def test_hashing_skipped_when_size_and_mtime_unchanged(tmp_path, monkeypatch):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    reanalyze(_project(tmp_path), cache_file)

    calls = []
    import analyzer.caching.change_detection as change_detection_module

    original = change_detection_module.compute_fingerprint

    def counting_compute_fingerprint(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(
        change_detection_module, "compute_fingerprint", counting_compute_fingerprint
    )
    reanalyze(_project(tmp_path), cache_file)

    assert calls == []  # size+mtime matched -> no re-hash


def test_save_and_load_cache_round_trip(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    cache_file = cache_path(tmp_path / ".ai-context")
    updated, *_ = reanalyze(_project(tmp_path), cache_file)

    cache, status = load_cache(cache_file, str(tmp_path))
    assert status is CacheStatus.VALID
    assert cache is not None
    assert cache.routes == updated.routes
    assert cache.modules == updated.modules


def test_save_cache_is_deterministic(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP, "models.py": "x = 1\n"})
    cache_file = cache_path(tmp_path / ".ai-context")
    updated, *_ = reanalyze(_project(tmp_path), cache_file)

    from analyzer.caching.models import CACHE_SCHEMA_VERSION, Cache

    cache = Cache(
        cache_version=CACHE_SCHEMA_VERSION,
        tool_version="x",
        repository_root=str(tmp_path),
        fingerprints={},
        entry_points=updated.entry_points,
        modules=updated.modules,
        routes=updated.routes,
        database_models=updated.database_models,
        imports=updated.imports,
        circular_imports=updated.circular_imports,
        module_dependencies=updated.module_dependencies,
        authentication=updated.authentication,
        configuration=updated.configuration,
        important_files=updated.important_files,
    )
    other_file = tmp_path / "other_cache.json"
    save_cache(other_file, cache)
    save_cache(other_file.with_name("other_cache2.json"), cache)
    assert other_file.read_text(encoding="utf-8") == other_file.with_name(
        "other_cache2.json"
    ).read_text(encoding="utf-8")
