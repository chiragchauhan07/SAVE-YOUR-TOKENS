"""Business logic for each MCP tool — no MCP SDK import anywhere in this file.

Pure functions: input in, a result dict out, or a real exception raised.
``tools.py`` is the only place that catches exceptions and converts them to
safe responses (D-035) — keeping these handlers callable and testable
directly, with no MCP harness required.

Every handler analyses a repository at most once, via ``analyzer.analyze_repository``,
and reuses the resulting ``Project`` for anything else it needs (a summary, a
Knowledge Base) — never a second scan, never a second AST parse.

Phase 6 added incremental capabilities (``incremental=True`` on
``handle_generate_knowledge_base``, plus ``handle_repository_changes`` and
``handle_clear_cache``) by reusing the top-level ``incremental`` package —
the same functions the CLI's ``update``/``cache-info``/``cache-clear``
commands call, not a second implementation (D-051).
"""

from __future__ import annotations

from pathlib import Path

from analyzer import Project, analyze_repository
from generator import generate_knowledge_base
from generator.writer import write_documents
from incremental import clear_cache as _clear_cache
from incremental import preview_changes, update_knowledge_base
from incremental.serialization import change_preview_dict, change_report_dict
from mcp_server.utils import build_health_status, build_repository_summary


def handle_analyze_repository(
    path: str,
    *,
    include_knowledge_base: bool = False,
    write_knowledge_base: bool = False,
    output_dir: str | None = None,
    overwrite: bool = True,
) -> dict[str, object]:
    """Scan, identify and understand a repository; optionally also generate
    (and optionally write) its Knowledge Base, from the same analysis.
    """
    project = analyze_repository(path)
    result: dict[str, object] = {"repository": build_repository_summary(project)}
    if include_knowledge_base or write_knowledge_base:
        result["knowledge_base"] = _build_knowledge_base_result(
            project,
            path,
            write=write_knowledge_base,
            output_dir=output_dir,
            overwrite=overwrite,
        )
    return result


def handle_repository_summary(path: str) -> dict[str, object]:
    """A fast, structured overview — analysis only, no Knowledge Base generation."""
    project = analyze_repository(path)
    return build_repository_summary(project)


def handle_generate_knowledge_base(
    path: str,
    *,
    output_dir: str | None = None,
    overwrite: bool = True,
    incremental: bool = False,
    force: bool = False,
) -> dict[str, object]:
    """Analyse a repository and write its Knowledge Base to disk.

    ``incremental=False`` (the default) preserves this tool's original
    Phase 5 behaviour exactly — a full analysis and an unconditional
    overwrite — so existing callers see no change. ``incremental=True``
    routes through the Phase 6 incremental engine instead: cached per-file
    results are reused wherever safe, and only documents whose rendered
    content actually changed are rewritten. ``force`` (only meaningful
    with ``incremental=True``) ignores the cache and re-analyses fully.
    """
    if incremental:
        report = update_knowledge_base(path, output_dir=output_dir, force=force)
        return change_report_dict(report)
    project = analyze_repository(path)
    return _build_knowledge_base_result(
        project, path, write=True, output_dir=output_dir, overwrite=overwrite
    )


def handle_repository_changes(
    path: str, *, output_dir: str | None = None
) -> dict[str, object]:
    """What would change on the next incremental update — read-only."""
    preview = preview_changes(path, output_dir=output_dir)
    return change_preview_dict(preview)


def handle_clear_cache(
    path: str, *, output_dir: str | None = None
) -> dict[str, object]:
    """Delete the incremental cache, forcing the next update to start fresh."""
    removed = _clear_cache(path, output_dir=output_dir)
    return {"cleared": removed}


def handle_health_check() -> dict[str, object]:
    return build_health_status()


def _build_knowledge_base_result(
    project: Project,
    path: str,
    *,
    write: bool,
    output_dir: str | None,
    overwrite: bool,
) -> dict[str, object]:
    resolved_output = Path(output_dir) if output_dir else Path(path) / ".ai-context"

    if write and not overwrite and _has_existing_content(resolved_output):
        return {
            "written": False,
            "skipped": True,
            "reason": "Output directory already contains files and overwrite is False.",
            "output_directory": str(resolved_output),
        }

    documents = generate_knowledge_base(project)
    total_bytes = sum(len(content.encode("utf-8")) for content in documents.values())

    if not write:
        return {
            "written": False,
            "skipped": False,
            "output_directory": str(resolved_output),
            "files": sorted(documents),
            "total_bytes": total_bytes,
        }

    written_paths = write_documents(documents, resolved_output)
    return {
        "written": True,
        "skipped": False,
        "output_directory": str(resolved_output),
        "files": sorted(written_path.name for written_path in written_paths),
        "total_bytes": total_bytes,
    }


def _has_existing_content(directory: Path) -> bool:
    return directory.is_dir() and any(directory.iterdir())
