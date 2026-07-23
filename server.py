"""MCP server entry point — placeholder.

Not implemented in Phase 1. This file exists to fix the shape of the final
architecture: the MCP layer is a thin adapter over :mod:`analyzer`, holding
no analysis logic of its own.

Planned surface (see docs/ROADMAP.md, Phase 5):

    Tool  ``analyze_repository(path)``
          Scan a repository and return its structured summary.
    Tool  ``generate_context(path, output_dir=".ai-context")``
          Write the AI-optimised context files to disk.
    Tool  ``get_context(path)``
          Return already-generated context without re-analysing.

Design rules for whoever implements this:

* Import from ``analyzer`` only. If the MCP layer needs new behaviour, add it
  to the engine and call it from here.
* Never import this module from ``analyzer``. The dependency points one way.
* Keep every tool deterministic. No LLM calls belong in this project's core.
"""

from __future__ import annotations


def main() -> None:
    """Run the MCP server over stdio. Not yet implemented."""
    raise NotImplementedError(
        "The MCP server arrives in Phase 5. Use `python cli.py scan <path>` "
        "to exercise the analysis engine today."
    )


if __name__ == "__main__":
    main()
