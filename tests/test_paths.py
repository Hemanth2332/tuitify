import json

import pytest

from tuitify import paths


@pytest.fixture
def home(tmp_path, monkeypatch):
    # Path.home() reads HOME on POSIX and USERPROFILE on Windows.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_config_dir_is_created_under_home(home):
    path = paths.config_dir()
    assert path == home / ".config" / "tuitify"
    assert path.is_dir()


def test_database_path(home):
    assert paths.database_path() == home / ".config" / "tuitify" / "recommendations.db"


def test_settings_seeded_from_packaged_default(home):
    path = paths.settings_path()
    assert path == home / ".config" / "tuitify" / "settings.json"
    assert path.read_text(encoding="utf-8") == paths.DEFAULT_SETTINGS_PATH.read_text(encoding="utf-8")


def test_existing_user_settings_not_overwritten(home):
    user_file = paths.config_dir() / "settings.json"
    user_file.write_text(json.dumps({"theme": "x"}), encoding="utf-8")
    paths.settings_path()
    assert json.loads(user_file.read_text(encoding="utf-8")) == {"theme": "x"}


def test_packaged_default_exists():
    assert paths.DEFAULT_SETTINGS_PATH.is_file()
