"""Small, dependency-free helpers shared across the analysis engine."""

from __future__ import annotations

from pathlib import Path

_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


def human_readable_size(size_bytes: int) -> str:
    """Format a byte count for display, e.g. ``1536`` -> ``"1.5 KB"``."""
    if size_bytes < 0:
        raise ValueError(f"size_bytes must be non-negative, got {size_bytes}")

    size = float(size_bytes)
    for unit in _SIZE_UNITS:
        if size < 1024 or unit == _SIZE_UNITS[-1]:
            # Whole bytes never need a decimal point.
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("unreachable")  # pragma: no cover


def is_hidden(name: str) -> bool:
    """Whether a file or directory name is dot-prefixed.

    ``.`` and ``..`` are never treated as hidden entries.
    """
    return name.startswith(".") and name not in {".", ".."}


def extension_of(name: str) -> str:
    """Lowercased extension of a file name, including the leading dot.

    Returns ``""`` for extensionless names and for dot-files such as
    ``.gitignore``, which are names rather than extensions.
    """
    return Path(name).suffix.lower()


def validate_repository_path(path: Path | str) -> Path:
    """Resolve ``path`` and confirm it is a usable repository root.

    Raises:
        FileNotFoundError: the path does not exist.
        NotADirectoryError: the path exists but is not a directory.
    """
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Repository path does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {resolved}")
    return resolved
