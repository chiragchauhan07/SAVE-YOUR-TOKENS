"""Output types for the Knowledge Base generator — not discovered facts.

These are presentation-layer types (a rendered document, ready to write to
disk), distinct from ``analyzer.models`` which holds facts the analysis
engine discovered. The generator organizes knowledge; it does not discover
any (see the package docstring in ``generator/__init__.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Document:
    """One generated Knowledge Base file, before its Related Context footer."""

    filename: str
    title: str
    #: One-line summary, used in INDEX.md and in other documents' Related
    #: Context links.
    description: str
    body: str
