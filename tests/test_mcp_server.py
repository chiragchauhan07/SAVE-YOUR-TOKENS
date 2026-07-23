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
