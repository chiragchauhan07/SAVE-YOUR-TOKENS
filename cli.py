"""Command-line interface for the Save your Tokens analysis engine.

Two commands:

- ``scan`` — scan a repository, identify it (languages, frameworks, package
  managers, build tools, CI/CD, containerization, configuration surfaces)
  and analyse its internal Python structure (entry points, routes, database
  models, authentication, configuration, imports, dependency relationships,
  important files). Prints a summary; exists to exercise and inspect the
  engine, not as the product.
- ``generate`` — run the same analysis and write the AI-native Knowledge
  Base (``.ai-context/`` by default) via ``generator``. This is the
  project's primary output; see ``docs/ARCHITECTURE.md``.

The MCP server (see ``server.py``) is the primary *interface*, once built.

Usage:
    python cli.py scan /path/to/repo
    python cli.py scan /path/to/repo --json
    python cli.py generate /path/to/repo
    python cli.py generate /path/to/repo --output /path/to/output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analyzer import Detection, Project, __version__, analyze_repository
from analyzer.serialization import project_to_dict
from analyzer.utils import human_readable_size
from generator import write_knowledge_base

#: How many important files the human-readable summary lists.
_TOP_IMPORTANT_FILES = 10

#: How many extensions the human-readable summary lists.
_TOP_EXTENSIONS = 15


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        project = analyze_repository(
            args.path,
            extra_ignored_directories=args.ignore,
            include_hidden=args.include_hidden,
            follow_symlinks=args.follow_symlinks,
        )
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.command == "generate":
        return _run_generate(project, args)
    return _run_scan(project, args)


def _run_scan(project: Project, args: argparse.Namespace) -> int:
    if args.json:
        json.dump(project_to_dict(project), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_summary(project)
    return 0


def _run_generate(project: Project, args: argparse.Namespace) -> int:
    output_dir = args.output or (args.path / ".ai-context")
    written = write_knowledge_base(project, output_dir)
    print(f"Generated {len(written)} files in {output_dir}")
    for path in written:
        print(f"  {path.name}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="save-your-tokens",
        description="Deterministic repository analysis for AI coding agents.",
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan a repository and report on it.")
    _add_analysis_arguments(scan)
    scan.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a summary.",
    )

    generate = subparsers.add_parser(
        "generate", help="Generate the .ai-context/ AI Knowledge Base."
    )
    _add_analysis_arguments(generate)
    generate.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory (default: <path>/.ai-context).",
    )

    return parser


def _add_analysis_arguments(subparser: argparse.ArgumentParser) -> None:
    """Arguments shared by every command that analyses a repository."""
    subparser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="Repository to analyse (default: current directory).",
    )
    subparser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="DIR",
        help="Extra directory name to ignore. Repeatable.",
    )
    subparser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include dot-prefixed files and directories.",
    )
    subparser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Descend into symlinked directories.",
    )


def _print_summary(project: Project) -> None:
    """Write a human-readable identity card and scan overview to stdout."""
    print(f"Repository  : {project.name}")
    if project.repository_type:
        print(f"Project Type: {project.repository_type.name}")
    print(f"Path        : {project.root}")

    if project.languages:
        print("\nLanguages:")
        for lang in project.languages:
            percentage = f"{lang.percentage:>5.1f}%"
            print(f"  {lang.name:<12} {percentage}  ({lang.file_count} files)")

    _print_detections("Frameworks", project.frameworks)
    _print_detections("Package Managers", project.package_managers)
    _print_detections("Build", project.build_tools)
    _print_detections("CI/CD", project.ci_providers)
    _print_detections("Containerization", project.container_tools)
    _print_detections("Environment", project.environment_files)

    if project.entry_points:
        print("\nEntry Points:")
        for entry_point in project.entry_points:
            print(f"  {entry_point.file} ({entry_point.kind})")

    if project.routes:
        print(f"\nBackend Routes: {len(project.routes)}")

    if project.database_models:
        print(f"\nDatabase Models: {len(project.database_models)}")

    _print_detections("Authentication", project.authentication)
    _print_detections("Main Configuration", project.configuration)

    if project.important_files:
        print("\nImportant Files:")
        for important_file in project.important_files[:_TOP_IMPORTANT_FILES]:
            print(f"  {important_file.file}")

    if project.circular_imports:
        print(f"\nCircular Imports: {len(project.circular_imports)} detected")

    if project.module_dependencies:
        count = len(project.module_dependencies)
        print(f"\nDependency Relationships: Available ({count})")

    stats = project.stats
    print(f"\nFiles      : {stats.total_files:,}")
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


def _print_detections(label: str, detections: tuple[Detection, ...]) -> None:
    if not detections:
        return
    print(f"\n{label}:")
    for detection in detections:
        print(f"  {detection.name}")


if __name__ == "__main__":
    raise SystemExit(main())
