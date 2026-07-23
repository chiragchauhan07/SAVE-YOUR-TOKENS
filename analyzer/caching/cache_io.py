"""Loading, saving and validating the persisted incremental cache.

Corruption, a schema version mismatch, or a tool version mismatch are all
treated the same way: don't trust it, fall back to full analysis (D-045).
Never attempt to migrate or partially trust a cache that doesn't match
exactly what this code expects to find — "never guess" applies to trusting
a cache file exactly as much as it applies to detection results.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from analyzer import __version__ as ENGINE_VERSION
from analyzer.caching.models import (
    CACHE_SCHEMA_VERSION,
    Cache,
    CacheStatus,
    FileFingerprint,
)
from analyzer.serialization import (
    database_model_dict,
    database_model_from_dict,
    detection_dict,
    detection_from_dict,
    entry_point_dict,
    entry_point_from_dict,
    import_edge_dict,
    import_edge_from_dict,
    important_file_dict,
    important_file_from_dict,
    module_dependency_dict,
    module_dependency_from_dict,
    module_dict,
    module_from_dict,
    route_dict,
    route_from_dict,
)

CACHE_FILENAME = "cache.json"


def cache_path(output_dir: Path) -> Path:
    """Where the cache lives, relative to a Knowledge Base output directory."""
    return output_dir / ".cache" / CACHE_FILENAME


def load_cache(path: Path, repository_root: str) -> tuple[Cache | None, CacheStatus]:
    """Load and validate the cache at ``path``.

    Returns ``(None, status)`` for anything that isn't a fully trustworthy
    cache — missing, corrupted, or from a different schema/tool version —
    and ``(cache, CacheStatus.VALID)`` otherwise. Never raises: a cache
    file is untrusted input by nature. ``repository_root`` is accepted for
    symmetry with the cache's own recorded root but is not itself an
    invalidation trigger — relative file paths inside the cache remain
    valid even if the repository directory was moved (D-050).
    """
    del repository_root  # see docstring: recorded, not validated
    if not path.is_file():
        return None, CacheStatus.MISSING
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, CacheStatus.CORRUPTED

    if not isinstance(raw, dict):
        return None, CacheStatus.CORRUPTED
    if raw.get("cache_version") != CACHE_SCHEMA_VERSION:
        return None, CacheStatus.VERSION_MISMATCH
    if raw.get("tool_version") != ENGINE_VERSION:
        return None, CacheStatus.TOOL_VERSION_MISMATCH

    try:
        cache = _cache_from_dict(raw)
    except (KeyError, TypeError, ValueError):
        return None, CacheStatus.CORRUPTED

    return cache, CacheStatus.VALID


def save_cache(path: Path, cache: Cache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(_cache_to_dict(cache), indent=2)
    path.write_text(content, encoding="utf-8", newline="\n")


def clear_cache(path: Path) -> bool:
    """Delete the cache file if present. Returns whether anything was removed."""
    if not path.is_file():
        return False
    path.unlink()
    with contextlib.suppress(OSError):
        path.parent.rmdir()  # remove the now-empty .cache/ directory too
    return True


def _cache_to_dict(cache: Cache) -> dict:
    return {
        "cache_version": cache.cache_version,
        "tool_version": cache.tool_version,
        "repository_root": cache.repository_root,
        "fingerprints": {
            path: {"size": fp.size, "mtime": fp.mtime, "content_hash": fp.content_hash}
            for path, fp in sorted(cache.fingerprints.items())
        },
        "entry_points": [entry_point_dict(ep) for ep in cache.entry_points],
        "modules": [module_dict(m) for m in cache.modules],
        "routes": [route_dict(r) for r in cache.routes],
        "database_models": [database_model_dict(m) for m in cache.database_models],
        "imports": [import_edge_dict(edge) for edge in cache.imports],
        "circular_imports": [list(cycle) for cycle in cache.circular_imports],
        "module_dependencies": [
            module_dependency_dict(dep) for dep in cache.module_dependencies
        ],
        "authentication": [detection_dict(d) for d in cache.authentication],
        "configuration": [detection_dict(d) for d in cache.configuration],
        "important_files": [important_file_dict(f) for f in cache.important_files],
    }


def _cache_from_dict(raw: dict) -> Cache:
    return Cache(
        cache_version=raw["cache_version"],
        tool_version=raw["tool_version"],
        repository_root=raw["repository_root"],
        fingerprints={
            path: FileFingerprint(
                size=fp["size"], mtime=fp["mtime"], content_hash=fp["content_hash"]
            )
            for path, fp in raw["fingerprints"].items()
        },
        entry_points=tuple(entry_point_from_dict(d) for d in raw["entry_points"]),
        modules=tuple(module_from_dict(d) for d in raw["modules"]),
        routes=tuple(route_from_dict(d) for d in raw["routes"]),
        database_models=tuple(
            database_model_from_dict(d) for d in raw["database_models"]
        ),
        imports=tuple(import_edge_from_dict(d) for d in raw["imports"]),
        circular_imports=tuple(tuple(cycle) for cycle in raw["circular_imports"]),
        module_dependencies=tuple(
            module_dependency_from_dict(d) for d in raw["module_dependencies"]
        ),
        authentication=tuple(detection_from_dict(d) for d in raw["authentication"]),
        configuration=tuple(detection_from_dict(d) for d in raw["configuration"]),
        important_files=tuple(
            important_file_from_dict(d) for d in raw["important_files"]
        ),
    )
