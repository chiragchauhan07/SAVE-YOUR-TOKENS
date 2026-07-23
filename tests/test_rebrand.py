"""Unit tests for the "Save your Tokens" -> Blueprint rebrand: the
``.ai-context/`` -> ``.blueprint/`` directory migration, graceful cache
fallback across the version bump, and the deprecated CLI/MCP/env-var
aliases kept for backwards compatibility (see docs/DECISIONS.md, D-053).
"""

from __future__ import annotations

import json
import sys

import cli
from analyzer.caching import CacheStatus
from generator.output import (
    DEFAULT_OUTPUT_DIRNAME,
    LEGACY_OUTPUT_DIRNAME,
    default_output_dir,
)
from incremental import update_knowledge_base
from mcp_server import server as mcp_server_module

_FLASK_APP = (
    "from flask import Flask\n"
    "app = Flask(__name__)\n\n"
    "@app.route('/health')\n"
    "def health():\n    return 'ok'\n"
)


def write_files(root, files: dict[str, str]) -> None:
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# --- generator.output.default_output_dir ------------------------------------


def test_default_output_dir_migrates_legacy_directory(tmp_path):
    legacy = tmp_path / LEGACY_OUTPUT_DIRNAME
    legacy.mkdir()
    (legacy / "OVERVIEW.md").write_text("stub", encoding="utf-8")

    resolved = default_output_dir(tmp_path)

    assert resolved == tmp_path / DEFAULT_OUTPUT_DIRNAME
    assert resolved.is_dir()
    assert (resolved / "OVERVIEW.md").read_text(encoding="utf-8") == "stub"
    assert not legacy.exists()


def test_default_output_dir_never_overwrites_existing_default(tmp_path):
    legacy = tmp_path / LEGACY_OUTPUT_DIRNAME
    legacy.mkdir()
    (legacy / "OVERVIEW.md").write_text("old", encoding="utf-8")

    current = tmp_path / DEFAULT_OUTPUT_DIRNAME
    current.mkdir()
    (current / "OVERVIEW.md").write_text("current", encoding="utf-8")

    resolved = default_output_dir(tmp_path)

    assert resolved == current
    assert (current / "OVERVIEW.md").read_text(encoding="utf-8") == "current"
    assert legacy.is_dir()  # left alone, not deleted or merged


def test_default_output_dir_no_op_when_neither_exists(tmp_path):
    resolved = default_output_dir(tmp_path)
    assert resolved == tmp_path / DEFAULT_OUTPUT_DIRNAME
    assert not resolved.exists()


# --- end-to-end: legacy directory + stale cache both recover gracefully -----


def test_update_knowledge_base_migrates_legacy_directory_and_cache(tmp_path):
    write_files(tmp_path, {"app.py": _FLASK_APP})
    update_knowledge_base(tmp_path)  # produces a real .blueprint/ + valid cache

    blueprint_dir = tmp_path / DEFAULT_OUTPUT_DIRNAME
    legacy_dir = tmp_path / LEGACY_OUTPUT_DIRNAME
    blueprint_dir.rename(legacy_dir)  # simulate a repo last touched pre-rebrand

    cache_file = legacy_dir / ".cache" / "cache.json"
    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    raw["tool_version"] = "0.6.0"  # the last "Save your Tokens" release
    cache_file.write_text(json.dumps(raw), encoding="utf-8")

    report = update_knowledge_base(tmp_path)

    assert blueprint_dir.is_dir()
    assert not legacy_dir.exists()
    assert report.cache_status is CacheStatus.TOOL_VERSION_MISMATCH
    assert report.forced_full_analysis is True
    assert (blueprint_dir / "OVERVIEW.md").is_file()


# --- deprecated CLI alias -------------------------------------------------


def test_cli_warns_on_legacy_script_invocation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["save-your-tokens", "scan", "sample_repo"])
    cli.main(["scan", "sample_repo"])
    err = capsys.readouterr().err
    assert "save-your-tokens" in err
    assert "blueprint" in err


def test_cli_silent_on_current_script_invocation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["blueprint", "scan", "sample_repo"])
    cli.main(["scan", "sample_repo"])
    err = capsys.readouterr().err
    assert err == ""


# --- deprecated MCP alias + env var -------------------------------------------------


def test_mcp_warns_on_legacy_script_invocation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["save-your-tokens-mcp"])
    mcp_server_module._warn_if_legacy_invocation()
    err = capsys.readouterr().err
    assert "save-your-tokens-mcp" in err
    assert "blueprint-mcp" in err


def test_mcp_silent_on_current_script_invocation(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["blueprint-mcp"])
    mcp_server_module._warn_if_legacy_invocation()
    err = capsys.readouterr().err
    assert err == ""


def test_mcp_log_level_prefers_new_env_var(monkeypatch):
    monkeypatch.setenv("BLUEPRINT_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SAVE_YOUR_TOKENS_LOG_LEVEL", "ERROR")
    assert mcp_server_module._resolve_log_level_name() == "DEBUG"


def test_mcp_log_level_falls_back_to_legacy_env_var(monkeypatch, caplog):
    monkeypatch.delenv("BLUEPRINT_LOG_LEVEL", raising=False)
    monkeypatch.setenv("SAVE_YOUR_TOKENS_LOG_LEVEL", "DEBUG")
    assert mcp_server_module._resolve_log_level_name() == "DEBUG"


def test_mcp_log_level_defaults_when_neither_set(monkeypatch):
    monkeypatch.delenv("BLUEPRINT_LOG_LEVEL", raising=False)
    monkeypatch.delenv("SAVE_YOUR_TOKENS_LOG_LEVEL", raising=False)
    assert mcp_server_module._resolve_log_level_name() == "WARNING"
