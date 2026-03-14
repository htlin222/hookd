"""Global configuration stored in ~/.config/hookd/.

Provides shared GitHub token and user-defined handler templates
that can be reused across multiple repositories.
"""

import shutil
from pathlib import Path

from hookd.constants import GLOBAL_CONFIG_DIR, GLOBAL_ENV_FILE, GLOBAL_TEMPLATES_DIR


def get_global_config_dir() -> Path:
    """Return the global config directory, respecting XDG_CONFIG_HOME."""
    xdg = Path.home() / ".config"
    return xdg / GLOBAL_CONFIG_DIR


def get_global_templates_dir() -> Path:
    return get_global_config_dir() / GLOBAL_TEMPLATES_DIR


def _parse_env_file(path: Path) -> dict[str, str]:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def load_global_env() -> dict[str, str]:
    """Load global environment variables from ~/.config/hookd/global.env."""
    path = get_global_config_dir() / GLOBAL_ENV_FILE
    return _parse_env_file(path)


def save_global_token(token: str) -> Path:
    """Save GitHub token to the global config for reuse across repos."""
    config_dir = get_global_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    env_path = config_dir / GLOBAL_ENV_FILE

    # Preserve existing entries, update token
    env = _parse_env_file(env_path)
    env["HOOKD_GITHUB_TOKEN"] = token

    lines = [f"{k}={v}" for k, v in env.items()]
    env_path.write_text("\n".join(lines) + "\n")
    return env_path


def get_global_token() -> str | None:
    """Retrieve the globally saved GitHub token, if any."""
    env = load_global_env()
    return env.get("HOOKD_GITHUB_TOKEN") or None


def list_global_templates() -> list[Path]:
    """List user-defined handler templates in ~/.config/hookd/templates/."""
    templates_dir = get_global_templates_dir()
    if not templates_dir.exists():
        return []
    return sorted(templates_dir.glob("*.sh"))


def copy_global_templates(dest_dir: Path) -> list[str]:
    """Copy all global handler templates into the target handlers directory.

    Returns list of copied filenames.
    """
    templates = list_global_templates()
    if not templates:
        return []

    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for tmpl in templates:
        dest = dest_dir / tmpl.name
        if not dest.exists():
            shutil.copy2(tmpl, dest)
            dest.chmod(0o755)
            copied.append(tmpl.name)
    return copied


def init_global_templates_dir() -> Path:
    """Ensure the global templates directory exists and return its path."""
    templates_dir = get_global_templates_dir()
    templates_dir.mkdir(parents=True, exist_ok=True)
    return templates_dir
