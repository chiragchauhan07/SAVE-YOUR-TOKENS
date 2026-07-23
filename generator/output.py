"""Where the Knowledge Base (and its incremental cache) live on disk.

One default location, resolved the same way by the CLI, the incremental
orchestrator and the MCP server, so all three agree on where an unspecified
``--output``/``output_dir`` points (D-053, the "Save your Tokens" ->
Blueprint rename). ``default_output_dir()`` also performs a one-time,
lossless migration of a directory still using the pre-rename name — a plain
filesystem rename, so an existing Knowledge Base and incremental cache
survive exactly as they were, not regenerated.
"""

from __future__ import annotations

from pathlib import Path

#: The Knowledge Base and incremental cache live here by default.
DEFAULT_OUTPUT_DIRNAME = ".blueprint"

#: Used by every release through 0.6.0 ("Save your Tokens"), before the
#: Blueprint rename.
LEGACY_OUTPUT_DIRNAME = ".ai-context"


def default_output_dir(root: Path) -> Path:
    """The default Knowledge Base directory for ``root``.

    If ``root / DEFAULT_OUTPUT_DIRNAME`` doesn't exist yet but
    ``root / LEGACY_OUTPUT_DIRNAME`` does (a repository last touched before
    the Blueprint rename), the legacy directory is renamed in place first.
    Never overwrites an existing ``.blueprint/`` directory, and never
    touches a caller-supplied custom output directory — this only applies
    to the default location.
    """
    default = root / DEFAULT_OUTPUT_DIRNAME
    legacy = root / LEGACY_OUTPUT_DIRNAME
    if not default.exists() and legacy.is_dir():
        legacy.rename(default)
    return default
