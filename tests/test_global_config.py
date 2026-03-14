"""Tests for hookd.global_config module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from hookd.global_config import (
    get_global_config_dir,
    get_global_templates_dir,
    load_global_env,
    save_global_token,
    get_global_token,
    list_global_templates,
    copy_global_templates,
    init_global_templates_dir,
)


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect ~/.config/hookd to a temp directory."""
    config_dir = tmp_path / ".config" / "hookd"
    monkeypatch.setattr(
        "hookd.global_config.get_global_config_dir",
        lambda: config_dir,
    )
    monkeypatch.setattr(
        "hookd.global_config.get_global_templates_dir",
        lambda: config_dir / "templates",
    )
    return config_dir


# ---------------------------------------------------------------------------
# load_global_env / get_global_token
# ---------------------------------------------------------------------------


def test_load_global_env_missing(fake_home):
    """Returns empty dict when global.env doesn't exist."""
    result = load_global_env()
    assert result == {}


def test_load_global_env_with_data(fake_home):
    """Parses global.env correctly."""
    fake_home.mkdir(parents=True, exist_ok=True)
    (fake_home / "global.env").write_text(
        "HOOKD_GITHUB_TOKEN=ghp_abc123\n"
        "# comment\n"
        "\n"
        "SOME_OTHER=value\n"
    )
    result = load_global_env()
    assert result["HOOKD_GITHUB_TOKEN"] == "ghp_abc123"
    assert result["SOME_OTHER"] == "value"
    assert len(result) == 2


def test_get_global_token_exists(fake_home):
    """Returns token when saved."""
    fake_home.mkdir(parents=True, exist_ok=True)
    (fake_home / "global.env").write_text("HOOKD_GITHUB_TOKEN=ghp_xyz\n")
    assert get_global_token() == "ghp_xyz"


def test_get_global_token_missing(fake_home):
    """Returns None when no token is saved."""
    assert get_global_token() is None


# ---------------------------------------------------------------------------
# save_global_token
# ---------------------------------------------------------------------------


def test_save_global_token_creates_file(fake_home):
    """Creates global.env if it doesn't exist."""
    path = save_global_token("ghp_newtoken")
    assert path.exists()
    content = path.read_text()
    assert "HOOKD_GITHUB_TOKEN=ghp_newtoken" in content


def test_save_global_token_preserves_existing(fake_home):
    """Preserves other entries when updating token."""
    fake_home.mkdir(parents=True, exist_ok=True)
    (fake_home / "global.env").write_text(
        "HOOKD_GITHUB_TOKEN=ghp_old\nOTHER_KEY=val\n"
    )
    save_global_token("ghp_new")
    content = (fake_home / "global.env").read_text()
    assert "HOOKD_GITHUB_TOKEN=ghp_new" in content
    assert "OTHER_KEY=val" in content


# ---------------------------------------------------------------------------
# list_global_templates / copy_global_templates
# ---------------------------------------------------------------------------


def test_list_global_templates_empty(fake_home):
    """Returns empty list when no templates exist."""
    assert list_global_templates() == []


def test_list_global_templates_finds_scripts(fake_home):
    """Finds .sh files in global templates dir."""
    tmpl_dir = fake_home / "templates"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "deploy.sh").write_text("#!/bin/bash\necho deploy")
    (tmpl_dir / "notify.sh").write_text("#!/bin/bash\necho notify")
    (tmpl_dir / "readme.txt").write_text("not a handler")

    templates = list_global_templates()
    names = [t.name for t in templates]
    assert "deploy.sh" in names
    assert "notify.sh" in names
    assert "readme.txt" not in names


def test_copy_global_templates(fake_home, tmp_path):
    """Copies global templates into destination directory."""
    tmpl_dir = fake_home / "templates"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "deploy.sh").write_text("#!/bin/bash\necho deploy")

    dest = tmp_path / "handlers"
    copied = copy_global_templates(dest)
    assert copied == ["deploy.sh"]
    assert (dest / "deploy.sh").exists()
    assert (dest / "deploy.sh").read_text() == "#!/bin/bash\necho deploy"


def test_copy_global_templates_no_overwrite(fake_home, tmp_path):
    """Does not overwrite existing handlers."""
    tmpl_dir = fake_home / "templates"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "deploy.sh").write_text("#!/bin/bash\necho NEW")

    dest = tmp_path / "handlers"
    dest.mkdir(parents=True)
    (dest / "deploy.sh").write_text("#!/bin/bash\necho EXISTING")

    copied = copy_global_templates(dest)
    assert copied == []
    assert (dest / "deploy.sh").read_text() == "#!/bin/bash\necho EXISTING"


# ---------------------------------------------------------------------------
# init_global_templates_dir
# ---------------------------------------------------------------------------


def test_init_global_templates_dir(fake_home):
    """Creates the global templates directory."""
    path = init_global_templates_dir()
    assert path.exists()
    assert path.is_dir()
