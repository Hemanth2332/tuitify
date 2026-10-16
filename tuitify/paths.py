"""Filesystem locations for Tuitify user data."""

from __future__ import annotations

import shutil
from pathlib import Path

APP_NAME = "tuitify"

# Packaged, read-only defaults shipped inside the wheel.
DEFAULT_SETTINGS_PATH = Path(__file__).parent / "tui" / "settings.json"


def config_dir() -> Path:
    """Return ~/.config/tuitify, creating it if needed."""
    path = Path.home() / ".config" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    """Path of the recommendations SQLite database."""
    return config_dir() / "recommendations.db"


def settings_path() -> Path:
    """User settings file; seeded from packaged defaults on first use."""
    path = config_dir() / "settings.json"
    if not path.exists() and DEFAULT_SETTINGS_PATH.is_file():
        try:
            shutil.copyfile(DEFAULT_SETTINGS_PATH, path)
        except OSError:
            pass  # Callers treat a missing settings file as empty.
    return path
