"""Unit tests for the Phase 6 CLI commands: update, cache-info, cache-clear.

``scan`` and ``generate`` are exercised manually across every phase's
verification (see docs/CONTRIBUTING.md) rather than duplicated here; this
file covers only what Phase 6 added.
"""

from __future__ import annotations

import json

import pytest

import cli

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


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text(_FLASK_APP, encoding="utf-8")
    return root


def test_update_command_first_run(repo, capsys):
    exit_code = cli.main(["update", str(repo)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Cache: missing" in out
    assert "Files analyzed: 1" in out
    assert "API_ROUTES.md" in out
    assert (repo / ".ai-context" / "OVERVIEW.md").is_file()


def test_update_command_second_run_no_changes(repo, capsys):
    cli.main(["update", str(repo)])
    capsys.readouterr()  # discard first run's output

    exit_code = cli.main(["update", str(repo)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Cache: valid" in out
    assert "Files analyzed: 0" in out
    assert "Knowledge unchanged: 12 document(s)" in out


def test_update_command_json_output(repo, capsys):
    cli.main(["update", str(repo), "--json"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["cache_status"] == "missing"
    assert set(data["documents_regenerated"]) == _EXPECTED_KB_FILES
    assert "change_set" in data


def test_update_command_force(repo, capsys):
    cli.main(["update", str(repo)])
    capsys.readouterr()

    exit_code = cli.main(["update", str(repo), "--force"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Full analysis performed" in out


def test_update_command_custom_output_dir(repo, tmp_path):
    output = tmp_path / "custom-kb"
    exit_code = cli.main(["update", str(repo), "--output", str(output)])
    assert exit_code == 0
    assert (output / "OVERVIEW.md").is_file()
    assert not (repo / ".ai-context").exists()


def test_update_command_nonexistent_path_errors_gracefully(capsys):
    exit_code = cli.main(["update", "definitely_missing_xyz"])
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "does not exist" in err


def test_cache_info_command_missing(repo, capsys):
    exit_code = cli.main(["cache-info", str(repo)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Exists       : False" in out
    assert "Status       : missing" in out


def test_cache_info_command_valid_after_update(repo, capsys):
    cli.main(["update", str(repo)])
    capsys.readouterr()

    cli.main(["cache-info", str(repo)])
    out = capsys.readouterr().out
    assert "Exists       : True" in out
    assert "Valid        : True" in out
    assert "Tracked files: 1" in out


def test_cache_info_command_json(repo, capsys):
    cli.main(["update", str(repo)])
    capsys.readouterr()

    cli.main(["cache-info", str(repo), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["exists"] is True
    assert data["valid"] is True
    assert data["tracked_files"] == 1


def test_cache_clear_command(repo, capsys):
    cli.main(["update", str(repo)])
    capsys.readouterr()

    exit_code = cli.main(["cache-clear", str(repo)])
    assert exit_code == 0
    assert "Cache cleared." in capsys.readouterr().out

    exit_code = cli.main(["cache-clear", str(repo)])
    assert exit_code == 0
    assert "No cache to clear." in capsys.readouterr().out


def test_update_after_cache_clear_is_full_run_again(repo, capsys):
    cli.main(["update", str(repo)])
    cli.main(["cache-clear", str(repo)])
    capsys.readouterr()

    cli.main(["update", str(repo)])
    out = capsys.readouterr().out
    assert "Cache: missing" in out
