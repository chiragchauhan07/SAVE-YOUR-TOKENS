"""Command-line interface for the Save your Tokens analysis engine.

Phase 1 exposes a single command, ``scan``, which reports what the scanner
found. It exists to exercise and inspect the engine; it is not the product.
The MCP server (see ``server.py``) is the primary interface.

Usage:
    python cli.py scan /path/to/repo
    python cli.py scan /path/to/repo --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analyzer import Project, __version__, scan_repository
from analyzer.utils import human_readable_size

#: How many extensions the human-readable summary lists.
_TOP_EXTENSIONS = 15


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        project = scan_repository(
            args.path,
            extra_ignored_directories=args.ignore,
            include_hidden=args.include_hidden,
            follow_symlinks=args.follow_symlinks,
        )
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.json:
        json.dump(_as_dict(project), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_summary(project)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="save-your-tokens",
        description="Deterministic repository analysis for AI coding agents.",
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="Scan a repository and report on it.")
    scan.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="Repository to scan (default: current directory).",
    )
    scan.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a summary.",
    )
    scan.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="DIR",
        help="Extra directory name to ignore. Repeatable.",
    )
    scan.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include dot-prefixed files and directories.",
    )
    scan.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Descend into symlinked directories.",
    )
    return parser


def _print_summary(project: Project) -> None:
    """Write a human-readable overview of a scan to stdout."""
    stats = project.stats
    print(f"Repository : {project.name}")
    print(f"Path       : {project.root}")
    print(f"Files      : {stats.total_files:,}")
    print(f"Directories: {stats.total_directories:,}")
    print(f"Total size : {human_readable_size(stats.total_size_bytes)}")

    if not stats.total_files:
        print("\nNo files matched the scan rules.")
        return

    print(f"\nFile types (top {_TOP_EXTENSIONS}):")
    for extension, count in list(stats.files_by_extension.items())[:_TOP_EXTENSIONS]:
        label = extension or "(no extension)"
        share = count / stats.total_files * 100
        print(f"  {label:<20} {count:>6,}  {share:>5.1f}%")

    print("\nLargest files:")
    for file in stats.largest_files:
        size = human_readable_size(file.size_bytes)
        print(f"  {size:>10}  {file.path}")


def _as_dict(project: Project) -> dict:
    """Convert a scan result to JSON-serialisable primitives."""
    stats = project.stats
    return {
        "name": project.name,
        "root": str(project.root),
        "stats": {
            "total_files": stats.total_files,
            "total_directories": stats.total_directories,
            "total_size_bytes": stats.total_size_bytes,
            "files_by_extension": stats.files_by_extension,
            "largest_files": [
                {"path": str(file.path), "size_bytes": file.size_bytes}
                for file in stats.largest_files
            ],
        },
        "files": [
            {
                "path": str(file.path),
                "size_bytes": file.size_bytes,
                "extension": file.extension,
            }
            for file in project.files
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
