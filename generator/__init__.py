"""Phase 4: turn a fully analysed Project into an AI-native Knowledge Base.

The generator never re-scans, re-parses or re-analyses anything — it
consumes only ``analyzer.models.Project``, already fully populated by
``scan_repository() -> identify_project() -> analyze_intelligence()`` (or
``analyzer.analyze_repository()``, which chains all three). Every fact in
every generated file traces back to a ``Project`` field; nothing here
invents or infers new information — the analyzer discovers knowledge, this
package only organizes it.

``generate_knowledge_base()`` returns ``{filename: markdown}``, pure and
side-effect free. ``write_knowledge_base()`` additionally writes those files
to disk. Kept separate so a caller (a future MCP tool, for instance) can get
the Knowledge Base as data without anything touching the filesystem.
"""

from __future__ import annotations

from pathlib import Path

from analyzer.models import Project
from generator import navigation
from generator.renderers import (
    ai_context,
    architecture,
    authentication,
    configuration,
    database,
    dependencies,
    important_files,
    index,
    modules,
    overview,
    project_structure,
    routes,
)
from generator.writer import write_documents

__all__ = ["generate_knowledge_base", "write_knowledge_base"]

#: Every renderer taking just ``Project``, in the order they populate the
#: Knowledge Base. ai_context and index are generated afterward — both need
#: the full document list, which doesn't exist until these have run.
_CONTENT_RENDERERS = (
    overview.render,
    project_structure.render,
    architecture.render,
    modules.render,
    dependencies.render,
    routes.render,
    database.render,
    authentication.render,
    configuration.render,
    important_files.render,
)


def generate_knowledge_base(project: Project) -> dict[str, str]:
    """Render the full Knowledge Base. Returns ``{filename: markdown}``."""
    documents = [renderer(project) for renderer in _CONTENT_RENDERERS]
    documents.append(ai_context.render(project, tuple(documents)))
    documents.append(index.render(tuple(documents)))

    descriptions = {document.filename: document.description for document in documents}
    return {
        document.filename: document.body
        + navigation.render_related_context(document.filename, descriptions)
        for document in documents
    }


def write_knowledge_base(project: Project, output_dir: Path) -> tuple[Path, ...]:
    """Generate and write the Knowledge Base to ``output_dir``."""
    return write_documents(generate_knowledge_base(project), output_dir)
