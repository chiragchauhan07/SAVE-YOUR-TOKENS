"""JSON-serialisable conversions for this package's own types.

Same reasoning as ``analyzer/serialization.py`` (D-034): one shared
implementation the CLI and the MCP server both import, not two that could
silently drift apart (D-051).
"""

from __future__ import annotations

from analyzer.caching.models import ChangeSet
from incremental.models import CacheInfo, ChangePreview, ChangeReport


def change_set_dict(change_set: ChangeSet) -> dict:
    return {
        "new_files": [str(path) for path in change_set.new_files],
        "modified_files": [str(path) for path in change_set.modified_files],
        "deleted_files": [str(path) for path in change_set.deleted_files],
        "renamed_files": [
            {"old": str(renamed.old_path), "new": str(renamed.new_path)}
            for renamed in change_set.renamed_files
        ],
        "unchanged_count": change_set.unchanged_count,
    }


def change_preview_dict(preview: ChangePreview) -> dict:
    return {
        "cache_status": preview.cache_status.value,
        "change_set": change_set_dict(preview.change_set),
    }


def change_report_dict(report: ChangeReport) -> dict:
    return {
        "cache_status": report.cache_status.value,
        "forced_full_analysis": report.forced_full_analysis,
        "change_set": change_set_dict(report.change_set),
        "files_analyzed": report.files_analyzed,
        "files_reused": report.files_reused,
        "documents_regenerated": list(report.documents_regenerated),
        "documents_unchanged": list(report.documents_unchanged),
        "new_routes": list(report.new_routes),
        "removed_routes": list(report.removed_routes),
        "new_models": list(report.new_models),
        "removed_models": list(report.removed_models),
        "changed_categories": list(report.changed_categories),
        "duration_seconds": report.duration_seconds,
    }


def cache_info_dict(info: CacheInfo) -> dict:
    return {
        "path": info.path,
        "exists": info.exists,
        "valid": info.valid,
        "status": info.status.value,
        "cache_version": info.cache_version,
        "tool_version": info.tool_version,
        "tracked_files": info.tracked_files,
    }
