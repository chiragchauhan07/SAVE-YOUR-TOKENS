"""Data shapes for the MCP integration layer — not discovered facts.

Like ``generator.models.Document``, these are presentation/response types
specific to this layer, not domain facts. They never duplicate anything in
``analyzer.models``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorType(StrEnum):
    """Every category of failure a tool call can report to a client.

    Deliberately small and closed — one value per case Phase 5's error
    handling requirements name explicitly (D-035).
    """

    NOT_FOUND = "repository_not_found"
    INVALID_REPOSITORY = "invalid_repository"
    PERMISSION_DENIED = "permission_denied"
    ANALYSIS_FAILED = "analysis_failed"
    GENERATION_FAILED = "generation_failed"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class ToolError:
    """A safe, client-facing error — never a raw exception message or traceback."""

    error_type: ErrorType
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.error_type.value, "message": self.message}
