"""MCP server entry point.

Thin by design, same role as ``cli.py``: this file just runs the real
implementation in ``mcp_server/``. The MCP SDK, tool definitions, error
handling and the stdio run loop all live there — nothing about repository
analysis or Knowledge Base generation happens in this module.

Usage:
    python server.py
    save-your-tokens-mcp     # once installed (see [project.scripts])

See docs/ARCHITECTURE.md for the tool surface (analyze_repository,
repository_summary, generate_knowledge_base, health_check) and
docs/CONTRIBUTING.md / README.md for MCP client configuration.
"""

from __future__ import annotations

from mcp_server.server import main

if __name__ == "__main__":
    main()
