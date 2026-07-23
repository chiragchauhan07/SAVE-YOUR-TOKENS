"""MCP server entry point.

stdio transport only, for now — FastMCP's own transport abstraction means
adding SSE or streamable-HTTP later is a one-line change to ``main()``, not
a rewrite (D-037).
"""

from __future__ import annotations

import logging
import os
import sys

from mcp_server.tools import mcp

_DEFAULT_LOG_LEVEL = "WARNING"


def _configure_logging() -> None:
    """Configure logging to stderr only.

    stdout is reserved for the MCP JSON-RPC stream on stdio transport —
    anything else written there corrupts the protocol (D-038). Quiet by
    default; set ``SAVE_YOUR_TOKENS_LOG_LEVEL=INFO`` or ``DEBUG`` for more
    detail during development.
    """
    level_name = os.environ.get(
        "SAVE_YOUR_TOKENS_LOG_LEVEL", _DEFAULT_LOG_LEVEL
    ).upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    """Run the MCP server over stdio."""
    _configure_logging()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
