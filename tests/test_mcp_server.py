"""Unit and integration tests for the Phase 5 MCP integration layer."""

from __future__ import annotations

import sys

import pytest

from generator import write_knowledge_base
from mcp_server import handlers
from mcp_server.errors import classify_exception
from mcp_server.models import ErrorType

_EXPECTED_TOOL_NAMES = {
    "analyze_repository",
    "repository_summary",
    "generate_knowledge_base",
    "repository_changes",
    "clear_cache",
    "health_check",
}

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


@pytest.fixture
def incremental_repo(tmp_path):
    """A small, writable Flask app — for tests that mutate a repo across
    multiple incremental calls (``sample_repo/`` is a static shared fixture
    other tests also depend on, so it can't be mutated).
    """
    repo = tmp_path / "incremental_repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n\n"
        "@app.route('/health')\n"
        "def health():\n    return 'ok'\n",
        encoding="utf-8",
    )
    return repo


# --- handlers: pure business logic, no MCP SDK involved


def test_handle_repository_summary_shape():
    summary = handlers.handle_repository_summary("sample_repo")
    assert summary["name"] == "sample_repo"
    assert summary["repository_type"]["name"] == "REST API"
    assert {lang["name"] for lang in summary["languages"]} == {"Python"}
    assert len(summary["routes"]) == 3
    assert summary["database_models"] == []


def test_handle_analyze_repository_without_knowledge_base():
    result = handlers.handle_analyze_repository("sample_repo")
    assert "repository" in result
    assert "knowledge_base" not in result


def test_handle_analyze_repository_includes_knowledge_base_without_writing(tmp_path):
    result = handlers.handle_analyze_repository(
        "sample_repo", include_knowledge_base=True, output_dir=str(tmp_path / "out")
    )
    kb = result["knowledge_base"]
    assert kb["written"] is False
    assert set(kb["files"]) == _EXPECTED_KB_FILES
    assert not (tmp_path / "out").exists()


def test_handle_analyze_repository_writes_knowledge_base(tmp_path):
    output_dir = tmp_path / "ai-context"
    result = handlers.handle_analyze_repository(
        "sample_repo", write_knowledge_base=True, output_dir=str(output_dir)
    )
    kb = result["knowledge_base"]
    assert kb["written"] is True
    assert set(kb["files"]) == _EXPECTED_KB_FILES
    assert output_dir.is_dir()
    assert (output_dir / "AI_CONTEXT.md").is_file()


def test_handle_generate_knowledge_base_writes_files(tmp_path):
    output_dir = tmp_path / "ai-context"
    result = handlers.handle_generate_knowledge_base(
        "sample_repo", output_dir=str(output_dir)
    )
    assert result["written"] is True
    assert set(result["files"]) == _EXPECTED_KB_FILES
    assert result["total_bytes"] > 0


def test_handle_generate_knowledge_base_respects_overwrite_false(tmp_path):
    output_dir = tmp_path / "ai-context"
    output_dir.mkdir()
    (output_dir / "stale.md").write_text("stale", encoding="utf-8")

    result = handlers.handle_generate_knowledge_base(
        "sample_repo", output_dir=str(output_dir), overwrite=False
    )
    assert result["written"] is False
    assert result["skipped"] is True
    # Nothing new was written; the stale file is untouched.
    assert [p.name for p in output_dir.iterdir()] == ["stale.md"]


def test_handle_generate_knowledge_base_overwrite_true_writes_over_existing(tmp_path):
    output_dir = tmp_path / "ai-context"
    output_dir.mkdir()
    (output_dir / "stale.md").write_text("stale", encoding="utf-8")

    result = handlers.handle_generate_knowledge_base(
        "sample_repo", output_dir=str(output_dir), overwrite=True
    )
    assert result["written"] is True
    assert (output_dir / "OVERVIEW.md").is_file()


def test_handle_generate_knowledge_base_analyzes_once_not_twice(tmp_path, monkeypatch):
    """Regression guard: one analysis call per tool call (Performance requirement)."""
    calls = []
    import mcp_server.handlers as handlers_module

    original = handlers_module.analyze_repository

    def counting_analyze(path, **kwargs):
        calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(handlers_module, "analyze_repository", counting_analyze)
    handlers.handle_generate_knowledge_base(
        "sample_repo", output_dir=str(tmp_path / "out")
    )
    assert len(calls) == 1


def test_handle_generate_knowledge_base_default_matches_original_full_behaviour(
    tmp_path,
):
    """incremental defaults to False — Phase 5 callers see no change."""
    result = handlers.handle_generate_knowledge_base(
        "sample_repo", output_dir=str(tmp_path / "out")
    )
    assert result["written"] is True
    assert set(result["files"]) == _EXPECTED_KB_FILES
    assert "cache_status" not in result  # the incremental-only shape


def test_handle_generate_knowledge_base_incremental_true(tmp_path, incremental_repo):
    result = handlers.handle_generate_knowledge_base(
        str(incremental_repo), output_dir=str(tmp_path / "out"), incremental=True
    )
    assert result["cache_status"] == "missing"
    assert set(result["documents_regenerated"]) == _EXPECTED_KB_FILES
    assert result["forced_full_analysis"] is True


def test_handle_generate_knowledge_base_incremental_second_call_is_selective(
    tmp_path, incremental_repo
):
    output_dir = str(tmp_path / "out")
    handlers.handle_generate_knowledge_base(
        str(incremental_repo), output_dir=output_dir, incremental=True
    )
    result = handlers.handle_generate_knowledge_base(
        str(incremental_repo), output_dir=output_dir, incremental=True
    )
    assert result["documents_regenerated"] == []
    assert set(result["documents_unchanged"]) == _EXPECTED_KB_FILES
    assert result["forced_full_analysis"] is False


def test_handle_repository_changes_is_read_only(tmp_path, incremental_repo):
    result = handlers.handle_repository_changes(
        str(incremental_repo), output_dir=str(tmp_path / "out")
    )
    assert result["cache_status"] == "missing"
    assert len(result["change_set"]["new_files"]) > 0
    assert not (tmp_path / "out").exists()


def test_handle_clear_cache(tmp_path, incremental_repo):
    output_dir = str(tmp_path / "out")
    handlers.handle_generate_knowledge_base(
        str(incremental_repo), output_dir=output_dir, incremental=True
    )
    result = handlers.handle_clear_cache(str(incremental_repo), output_dir=output_dir)
    assert result["cleared"] is True

    result_again = handlers.handle_clear_cache(
        str(incremental_repo), output_dir=output_dir
    )
    assert result_again["cleared"] is False


def test_handle_health_check_shape():
    status = handlers.handle_health_check()
    assert status["status"] == "ok"
    assert status["package_version"]
    assert status["python_version"]
    assert status["platform"]


def test_handlers_raise_on_missing_repository():
    with pytest.raises(FileNotFoundError):
        handlers.handle_repository_summary("this_path_does_not_exist_xyz")


def test_handlers_raise_on_file_instead_of_directory(tmp_path):
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        handlers.handle_repository_summary(str(file_path))


# --- error classification


def test_classify_file_not_found():
    error = classify_exception(
        FileNotFoundError("Repository path does not exist: /x"), phase="analysis"
    )
    assert error.error_type is ErrorType.NOT_FOUND
    assert "does not exist" in error.message


def test_classify_not_a_directory():
    error = classify_exception(
        NotADirectoryError("Repository path is not a directory: /x"), phase="analysis"
    )
    assert error.error_type is ErrorType.INVALID_REPOSITORY


def test_classify_permission_error_analysis_phase():
    error = classify_exception(PermissionError("denied"), phase="analysis")
    assert error.error_type is ErrorType.PERMISSION_DENIED
    assert "reading" in error.message


def test_classify_permission_error_generation_phase():
    error = classify_exception(PermissionError("denied"), phase="generation")
    assert error.error_type is ErrorType.PERMISSION_DENIED
    assert "writing" in error.message


def test_classify_unexpected_exception_never_leaks_message():
    error = classify_exception(
        ValueError("sensitive internal detail: /etc/passwd"), phase="analysis"
    )
    assert error.error_type is ErrorType.ANALYSIS_FAILED
    assert "sensitive" not in error.message
    assert "/etc/passwd" not in error.message


def test_classify_generation_failure_never_leaks_message():
    error = classify_exception(RuntimeError("db password=hunter2"), phase="generation")
    assert error.error_type is ErrorType.GENERATION_FAILED
    assert "hunter2" not in error.message


def test_classify_health_phase_fallback():
    error = classify_exception(RuntimeError("boom"), phase="health")
    assert error.error_type is ErrorType.INTERNAL_ERROR


# --- tools: FastMCP registration and in-process invocation


@pytest.mark.anyio
async def test_all_tools_registered():
    from mcp_server.tools import mcp

    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == _EXPECTED_TOOL_NAMES


@pytest.mark.anyio
async def test_health_check_tool_call():
    from mcp_server.tools import mcp

    _, data = await mcp.call_tool("health_check", {})
    assert data["success"] is True
    assert data["status"] == "ok"


@pytest.mark.anyio
async def test_repository_summary_tool_call():
    from mcp_server.tools import mcp

    _, data = await mcp.call_tool("repository_summary", {"path": "sample_repo"})
    assert data["success"] is True
    assert data["name"] == "sample_repo"


@pytest.mark.anyio
async def test_analyze_repository_tool_call_nonexistent_path_never_raises():
    """The server must never crash on a client-supplied bad path."""
    from mcp_server.tools import mcp

    _, data = await mcp.call_tool(
        "analyze_repository", {"path": "definitely_missing_xyz"}
    )
    assert data["success"] is False
    assert data["error"]["type"] == "repository_not_found"
    assert "Traceback" not in data["error"]["message"]


@pytest.mark.anyio
async def test_generate_knowledge_base_tool_call(tmp_path):
    from mcp_server.tools import mcp

    output_dir = tmp_path / "kb"
    _, data = await mcp.call_tool(
        "generate_knowledge_base",
        {"path": "sample_repo", "output_dir": str(output_dir)},
    )
    assert data["success"] is True
    assert data["written"] is True
    assert set(data["files"]) == _EXPECTED_KB_FILES


@pytest.mark.anyio
async def test_generate_knowledge_base_tool_call_incremental(
    tmp_path, incremental_repo
):
    from mcp_server.tools import mcp

    output_dir = tmp_path / "kb"
    _, first = await mcp.call_tool(
        "generate_knowledge_base",
        {
            "path": str(incremental_repo),
            "output_dir": str(output_dir),
            "incremental": True,
        },
    )
    assert first["success"] is True
    assert set(first["documents_regenerated"]) == _EXPECTED_KB_FILES

    _, second = await mcp.call_tool(
        "generate_knowledge_base",
        {
            "path": str(incremental_repo),
            "output_dir": str(output_dir),
            "incremental": True,
        },
    )
    assert second["documents_regenerated"] == []
    assert set(second["documents_unchanged"]) == _EXPECTED_KB_FILES


@pytest.mark.anyio
async def test_repository_changes_tool_call(tmp_path, incremental_repo):
    from mcp_server.tools import mcp

    output_dir = tmp_path / "kb"
    _, data = await mcp.call_tool(
        "repository_changes",
        {"path": str(incremental_repo), "output_dir": str(output_dir)},
    )
    assert data["success"] is True
    assert data["cache_status"] == "missing"
    assert len(data["change_set"]["new_files"]) == 1
    assert not output_dir.exists()  # read-only: nothing written


@pytest.mark.anyio
async def test_clear_cache_tool_call(tmp_path, incremental_repo):
    from mcp_server.tools import mcp

    output_dir = tmp_path / "kb"
    await mcp.call_tool(
        "generate_knowledge_base",
        {
            "path": str(incremental_repo),
            "output_dir": str(output_dir),
            "incremental": True,
        },
    )
    _, data = await mcp.call_tool(
        "clear_cache", {"path": str(incremental_repo), "output_dir": str(output_dir)}
    )
    assert data["success"] is True
    assert data["cleared"] is True


@pytest.mark.anyio
async def test_clear_cache_tool_call_nonexistent_path_never_raises():
    """clear_cache only ever checks for a cache *file*; a repository path
    that doesn't exist just means there's nothing to clear — not an error.
    """
    from mcp_server.tools import mcp

    _, data = await mcp.call_tool("clear_cache", {"path": "missing_xyz"})
    assert data["success"] is True
    assert data["cleared"] is False


@pytest.mark.anyio
async def test_multiple_sequential_tool_calls_are_independent():
    """Repeated calls against the same repository return consistent results —
    no shared mutable state leaking between requests.
    """
    from mcp_server.tools import mcp

    results = []
    for _ in range(3):
        _, data = await mcp.call_tool("repository_summary", {"path": "sample_repo"})
        results.append(data)
    assert all(r == results[0] for r in results)


@pytest.mark.anyio
async def test_malformed_request_missing_required_argument_does_not_crash_server():
    from mcp_server.tools import mcp

    with pytest.raises(Exception):  # noqa: B017 - FastMCP raises its own validation error
        await mcp.call_tool("repository_summary", {})
    # The server (the FastMCP instance) is still usable afterward.
    tools = await mcp.list_tools()
    assert {tool.name for tool in tools} == _EXPECTED_TOOL_NAMES


# --- determinism: MCP output must match CLI output exactly


def test_mcp_generated_knowledge_base_matches_cli_generated_knowledge_base(tmp_path):
    from analyzer import analyze_repository

    mcp_output = tmp_path / "via_mcp"
    cli_output = tmp_path / "via_cli"

    handlers.handle_generate_knowledge_base("sample_repo", output_dir=str(mcp_output))
    project = analyze_repository("sample_repo")
    write_knowledge_base(project, cli_output)

    for filename in _EXPECTED_KB_FILES:
        assert (mcp_output / filename).read_bytes() == (
            cli_output / filename
        ).read_bytes()


def test_mcp_incremental_output_matches_cli_update_output(incremental_repo, tmp_path):
    from incremental import update_knowledge_base as cli_update_knowledge_base

    mcp_output = tmp_path / "via_mcp"
    cli_output = tmp_path / "via_cli"

    handlers.handle_generate_knowledge_base(
        str(incremental_repo), output_dir=str(mcp_output), incremental=True
    )
    cli_update_knowledge_base(incremental_repo, output_dir=cli_output)

    for filename in _EXPECTED_KB_FILES:
        assert (mcp_output / filename).read_bytes() == (
            cli_output / filename
        ).read_bytes()


# --- real stdio transport integration test


@pytest.mark.anyio
async def test_stdio_transport_end_to_end():
    """Spawns the real server.py as a subprocess and speaks real MCP
    protocol over stdio — the same transport a real client (Claude Code,
    Cursor) uses. Slower than the in-process tests above; kept as the one
    test that proves the actual transport, not just the tool functions.
    """
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command=sys.executable, args=["server.py"])
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert {tool.name for tool in tools.tools} == _EXPECTED_TOOL_NAMES

        result = await session.call_tool("health_check", {})
        assert result.structuredContent is not None
        assert result.structuredContent["success"] is True
        assert result.isError is False

        bad_result = await session.call_tool(
            "analyze_repository", {"path": "missing_xyz"}
        )
        assert bad_result.structuredContent["success"] is False
    # Exiting both async context managers above tears the subprocess down
    # cleanly — reaching this line at all is the graceful-shutdown assertion.
