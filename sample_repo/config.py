"""Fixture configuration surface, for Phase 3 configuration detection."""

import os

SETTINGS = {
    "debug": os.getenv("SAMPLE_DEBUG", "false") == "true",
    "database_url": os.getenv("SAMPLE_DATABASE_URL", "sqlite:///notes.db"),
    "port": int(os.getenv("SAMPLE_PORT", "5000")),
}
