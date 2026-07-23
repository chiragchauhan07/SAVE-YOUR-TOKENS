"""MCP tool definitions — the only module in this project that imports the
MCP SDK.

Every tool is a thin wrapper: validate nothing itself (the engine already
does — see ``analyzer.utils.validate_repository_path``), call exactly one
``handlers`` function, and convert its result or exception into a safe,
structured response via ``_run``. No tool here ever lets a raw exception
propagate to the MCP SDK — FastMCP's own exception wrapping echoes
``str(exception)`` verbatim into the client-facing error, which is not
guaranteed safe (confirmed by direct testing while designing this phase);
catching everything ourselves is the only way to guarantee D-035's
"never expose internals" rule.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from mcp_server import handlers
from mcp_server.errors import Phase, classify_exception

logger = logging.getLogger(__name__)

mcp = FastMCP("save-your-tokens")


@mcp.tool()
def analyze_repository(
    path: str,
    include_knowledge_base: bool = False,
    write_knowledge_base: bool = False,
    output_dir: str | None = None,
    overwrite: bool = True,
) -> dict[str, object]:
    """Analyze a repository: scan it, identify its technology stack, and
    understand its Python structure. Set include_knowledge_base to also
    generate the AI Knowledge Base in the same call, and write_knowledge_base
    to write it to output_dir (default: <path>/.ai-context).
    """
    return _run(
        "analysis",
        lambda: handlers.handle_analyze_repository(
            path,
            include_knowledge_base=include_knowledge_base,
            write_knowledge_base=write_knowledge_base,
            output_dir=output_dir,
            overwrite=overwrite,
        ),
    )


@mcp.tool()
def repository_summary(path: str) -> dict[str, object]:
    """A fast, structured overview of a repository: type, languages,
    frameworks, entry points, routes, database models, important files,
    authentication and configuration. Does not generate the Knowledge Base.
    """
    return _run("analysis", lambda: handlers.handle_repository_summary(path))


@mcp.tool()
def generate_knowledge_base(
    path: str, output_dir: str | None = None, overwrite: bool = True
) -> dict[str, object]:
    """Generate the .ai-context/ AI Knowledge Base for a repository and
    write it to disk (default: <path>/.ai-context). Returns generation
    statistics — file names and byte counts, never document content.
    """
    return _run(
        "generation",
        lambda: handlers.handle_generate_knowledge_base(
            path, output_dir=output_dir, overwrite=overwrite
        ),
    )


@mcp.tool()
def health_check() -> dict[str, object]:
    """Package, server and environment version information — for
    diagnosing an installation.
    """
    return _run("health", handlers.handle_health_check)


def _run(phase: Phase, call: Callable[[], dict[str, object]]) -> dict[str, object]:
    """Run one handler call, converting any exception into a safe response.

    Never re-raises: the server must never crash on a client-supplied
    repository path, and no client ever sees a traceback (D-035).
    """
    try:
        result = call()
    except Exception as exc:
        logger.exception("MCP tool call failed during %s", phase)
        error = classify_exception(exc, phase=phase)
        return {"success": False, "error": error.to_dict()}
    return {"success": True, **result}
