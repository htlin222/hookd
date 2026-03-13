import platform
import shutil
import subprocess
from pathlib import Path


def detect_service_manager() -> str | None:
    system = platform.system()
    if system == "Linux" and shutil.which("systemctl"):
        return "systemd"
    if system == "Darwin" and shutil.which("launchctl"):
        return "launchd"
    return None


def generate_env_file(
    path: Path,
    secret: str,
    github_token: str,
    port: int,
    repo: str = "",
) -> None:
    lines = [
        f"HOOKD_SECRET={secret}",
        f"HOOKD_GITHUB_TOKEN={github_token}",
        f"HOOKD_PORT={port}",
    ]
    if repo:
        lines.append(f"HOOKD_REPO={repo}")
    path.write_text("\n".join(lines) + "\n")


def generate_service_file(
    manager: str,
    workdir: str,
    port: int,
    python_path: str | None = None,
) -> str:
    if python_path is None:
        python_path = shutil.which("python3") or "python3"

    if manager == "systemd":
        return _generate_systemd(workdir, port, python_path)
    elif manager == "launchd":
        return _generate_launchd(workdir, port, python_path)
    else:
        raise ValueError(f"Unknown service manager: {manager}")


def _generate_systemd(workdir: str, port: int, python_path: str) -> str:
    return f"""[Unit]
Description=hookd - GitHub webhook listener
After=network.target tailscaled.service

[Service]
Type=simple
WorkingDirectory={workdir}
EnvironmentFile={workdir}/.hookd/.env
ExecStart={python_path} -m hookd.listener --config {workdir}/.hookd/config.yaml --port {port}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def _generate_launchd(workdir: str, port: int, python_path: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hookd.listener</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>hookd.listener</string>
        <string>--config</string>
        <string>{workdir}/.hookd/config.yaml</string>
        <string>--port</string>
        <string>{port}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{workdir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{workdir}/.hookd/hookd.log</string>
    <key>StandardErrorPath</key>
    <string>{workdir}/.hookd/hookd.err</string>
</dict>
</plist>
"""


def install_service(manager: str, content: str, workdir: str) -> Path:
    if manager == "systemd":
        path = Path.home() / ".config" / "systemd" / "user" / "hookd.service"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "hookd"], check=True)
        return path
    elif manager == "launchd":
        path = Path.home() / "Library" / "LaunchAgents" / "com.hookd.listener.plist"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path
    else:
        raise ValueError(f"Unknown service manager: {manager}")
