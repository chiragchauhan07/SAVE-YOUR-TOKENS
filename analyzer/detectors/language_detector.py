"""Programming/markup language detection from file extensions.

Purely structural: an extension either maps to a known language or it
doesn't. No content is read.
"""

from __future__ import annotations

from collections import Counter

from analyzer.detectors.signatures import LANGUAGE_EXTENSIONS
from analyzer.models import LanguageStat, Project


def detect_languages(project: Project) -> tuple[LanguageStat, ...]:
    """Aggregate file count and size per language, ordered by prevalence.

    Prevalence is measured by total bytes, not file count, so a handful of
    large source files outweigh many tiny ones — closer to "how much of this
    codebase is X" than "how many X files exist".
    """
    file_counts: Counter[str] = Counter()
    size_totals: Counter[str] = Counter()

    for file in project.files:
        language = LANGUAGE_EXTENSIONS.get(file.extension)
        if language is None:
            continue
        file_counts[language] += 1
        size_totals[language] += file.size_bytes

    total_size = sum(size_totals.values())
    if not total_size:
        return ()

    stats = (
        LanguageStat(
            name=language,
            file_count=file_counts[language],
            size_bytes=size_bytes,
            percentage=round(size_bytes / total_size * 100, 1),
        )
        for language, size_bytes in size_totals.items()
    )
    return tuple(sorted(stats, key=lambda stat: (-stat.size_bytes, stat.name)))
