"""MCP server entry point.

stdio transport only, for now — FastMCP's own transport abstraction means
adding SSE or streamable-HTTP later is a one-line change to ``main()``, not
a rewrite (D-037).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from mcp_server.tools import mcp

_DEFAULT_LOG_LEVEL = "WARNING"

#: Renamed from ``SAVE_YOUR_TOKENS_LOG_LEVEL`` in the Blueprint rebrand; the
#: old name is still honoured as a deprecated fallback (see D-053).
_LOG_LEVEL_ENV_VAR = "BLUEPRINT_LOG_LEVEL"
_LEGACY_LOG_LEVEL_ENV_VAR = "SAVE_YOUR_TOKENS_LOG_LEVEL"

#: The pre-rename console script name; still installed as a deprecated
#: alias (see [project.scripts] in pyproject.toml).
_LEGACY_SCRIPT_NAME = "save-your-tokens-mcp"


def _configure_logging() -> None:
    """Configure logging to stderr only.

    stdout is reserved for the MCP JSON-RPC stream on stdio transport —
    anything else written there corrupts the protocol (D-038). Quiet by
    default; set ``BLUEPRINT_LOG_LEVEL=INFO`` or ``DEBUG`` for more detail
    during development.
    """
    level_name = _resolve_log_level_name()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _resolve_log_level_name() -> str:
    if _LOG_LEVEL_ENV_VAR in os.environ:
        return os.environ[_LOG_LEVEL_ENV_VAR].upper()
    if _LEGACY_LOG_LEVEL_ENV_VAR in os.environ:
        logging.getLogger(__name__).warning(
            "%s is deprecated, use %s instead.",
            _LEGACY_LOG_LEVEL_ENV_VAR,
            _LOG_LEVEL_ENV_VAR,
        )
        return os.environ[_LEGACY_LOG_LEVEL_ENV_VAR].upper()
    return _DEFAULT_LOG_LEVEL


def _warn_if_legacy_invocation() -> None:
    """A one-time deprecation notice when launched via the old script name."""
    if Path(sys.argv[0]).stem == _LEGACY_SCRIPT_NAME:
        print(
            f"warning: '{_LEGACY_SCRIPT_NAME}' is deprecated, use "
            "'blueprint-mcp' instead.",
            file=sys.stderr,
        )


def main() -> None:
    """Run the MCP server over stdio."""
    _warn_if_legacy_invocation()
    _configure_logging()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
