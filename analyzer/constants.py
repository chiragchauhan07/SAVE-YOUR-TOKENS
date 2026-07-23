"""Deterministic ignore rules and scanner tuning constants.

These sets are intentionally *data*, not logic. Adding support for a new
ecosystem should mean adding entries here, never editing the scanner.
"""

from __future__ import annotations

from typing import Final

#: Directory names pruned during the walk. Matched on the directory's own
#: name (not its path), so they apply at any depth.
IGNORED_DIRECTORIES: Final[frozenset[str]] = frozenset(
    {
        # Version control / tooling metadata
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        # Python
        "__pycache__",
        ".venv",
        "venv",
        "env",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".eggs",
        "site-packages",
        # JavaScript / TypeScript
        "node_modules",
        "bower_components",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".turbo",
        ".parcel-cache",
        # Build / distribution output
        "build",
        "dist",
        "out",
        "target",
        "obj",
        # Other ecosystems
        "vendor",
        ".gradle",
        ".dart_tool",
        ".terraform",
        # Coverage / caches
        "coverage",
        "htmlcov",
        ".cache",
        ".sass-cache",
        # This tool's own output — current name plus the pre-rename name
        # ("Save your Tokens"), so a repository not yet migrated (see
        # generator/output.py) still isn't scanned as source.
        ".blueprint",
        ".ai-context",
    }
)

#: Exact file names that never carry repository signal.
IGNORED_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".DS_Store",
        "Thumbs.db",
        "desktop.ini",
    }
)

#: Extensions (lowercase, leading dot) for compiled artefacts, media and
#: archives. These are noise for an AI reading a repository.
IGNORED_FILE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        # Compiled / linked artefacts
        ".pyc",
        ".pyo",
        ".pyd",
        ".class",
        ".o",
        ".obj",
        ".a",
        ".lib",
        ".so",
        ".dylib",
        ".dll",
        ".exe",
        ".wasm",
        # Archives
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".jar",
        ".war",
        # Images / media
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".tiff",
        ".svg",
        ".mp3",
        ".wav",
        ".ogg",
        ".mp4",
        ".mov",
        ".avi",
        ".webm",
        # Fonts
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        # Documents / binaries
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Databases / dumps
        ".db",
        ".sqlite",
        ".sqlite3",
        ".mdb",
        # Misc noise
        ".log",
        ".tmp",
        ".swp",
        ".bak",
        ".map",
    }
)

#: How many entries `RepositoryStats.largest_files` retains.
LARGEST_FILES_COUNT: Final[int] = 10
