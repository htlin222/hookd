import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

from hookd.constants import HOOKD_DIR, CONFIG_FILE, ENV_FILE, DEFAULT_PORT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hookd",
        description="GitHub webhook listener via Tailscale Funnel",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Launch the setup wizard")

    sub.add_parser("status", help="Show service and funnel status")

    sub.add_parser("logs", help="Tail service logs")

    test_parser = sub.add_parser("test", help="Send a test webhook event")
    test_parser.add_argument(
        "--event", default="push", help="Event type to simulate (default: push)"
    )
    test_parser.add_argument(
        "--port", type=int, default=None, help="Port to send to"
    )

    sub.add_parser("edit", help="Open config in $EDITOR")

    sub.add_parser("rotate", help="Rotate webhook secret")

    sub.add_parser("disable", help="Stop service and close funnel")

    sub.add_parser("enable", help="Start service and open funnel")

    return parser


def _load_env(workdir: Path) -> dict[str, str]:
    env_path = workdir / HOOKD_DIR / ENV_FILE
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def _get_port(env: dict[str, str], args_port: int | None = None) -> int:
    if args_port:
        return args_port
    return int(env.get("HOOKD_PORT", str(DEFAULT_PORT)))


def cmd_setup(args, workdir: Path):
    from hookd.steps.detect import detect_git_context
    from hookd.tui.app import HookdApp

    ctx = detect_git_context(workdir)
    context = {
        "workdir": str(workdir),
        "owner": ctx.owner,
        "repo": ctx.repo,
        "branch": ctx.branch,
        "full_name": ctx.full_name,
        "remote_url": ctx.remote_url,
    }
    app = HookdApp(context=context)
    app.run()


def cmd_status(args, workdir: Path):
    from hookd.steps.system import detect_service_manager
    from hookd.steps.funnel import check_funnel_status, get_tailscale_hostname

    env = _load_env(workdir)
    port = _get_port(env)

    manager = detect_service_manager()
    print(f"Service manager: {manager or 'none detected'}")

    if manager == "systemd":
        result = subprocess.run(
            ["systemctl", "--user", "status", "hookd"],
            capture_output=True, text=True,
        )
        print(result.stdout)
    elif manager == "launchd":
        result = subprocess.run(
            ["launchctl", "list", "com.hookd.listener"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("Service: running")
            print(result.stdout)
        else:
            print("Service: not loaded")

    hostname = get_tailscale_hostname()
    if hostname:
        print(f"Tailscale hostname: {hostname}")
        print(f"Funnel URL: https://{hostname}:{port}/webhook")
    else:
        print("Tailscale: not detected")


def cmd_logs(args, workdir: Path):
    from hookd.steps.system import detect_service_manager

    manager = detect_service_manager()
    if manager == "systemd":
        os.execvp("journalctl", ["journalctl", "--user", "-u", "hookd", "-f"])
    elif manager == "launchd":
        log_file = workdir / HOOKD_DIR / "hookd.log"
        if log_file.exists():
            os.execvp("tail", ["tail", "-f", str(log_file)])
        else:
            print(f"Log file not found: {log_file}")
    else:
        print("No service manager detected. Run the listener manually:")
        print(f"  python -m hookd.listener --config {workdir / HOOKD_DIR / CONFIG_FILE}")


def cmd_test(args, workdir: Path):
    import urllib.request

    env = _load_env(workdir)
    secret = env.get("HOOKD_SECRET", "")
    port = _get_port(env, args.port)

    if not secret:
        print("Error: No HOOKD_SECRET found in .env")
        sys.exit(1)

    event = args.event
    if event == "push":
        payload = {
            "ref": "refs/heads/main",
            "repository": {"full_name": "test/repo", "html_url": "https://github.com/test/repo"},
            "sender": {"login": "hookd-test"},
            "pusher": {"name": "hookd-test"},
            "commits": [{"message": "test commit from hookd", "id": "test123"}],
        }
    else:
        payload = {
            "action": "opened",
            "repository": {"full_name": "test/repo", "html_url": "https://github.com/test/repo"},
            "sender": {"login": "hookd-test"},
        }

    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/webhook",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": f"hookd-test-{os.urandom(4).hex()}",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        print(f"Response: {json.dumps(data, indent=2)}")
    except urllib.error.URLError as e:
        print(f"Error: Could not connect to listener on port {port}")
        print(f"  {e}")
        sys.exit(1)


def cmd_edit(args, workdir: Path):
    config_path = workdir / HOOKD_DIR / CONFIG_FILE
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        print("Run 'hookd setup' first.")
        sys.exit(1)

    editor = os.environ.get("EDITOR", "vim")
    os.execvp(editor, [editor, str(config_path)])


def cmd_rotate(args, workdir: Path):
    import secrets as secrets_mod
    from hookd.steps.github import list_webhooks, update_webhook_secret

    env = _load_env(workdir)
    token = env.get("HOOKD_GITHUB_TOKEN", "")
    if not token:
        print("Error: No HOOKD_GITHUB_TOKEN in .env")
        sys.exit(1)

    new_secret = secrets_mod.token_hex(32)

    # Update .env
    env_path = workdir / HOOKD_DIR / ENV_FILE
    from hookd.steps.system import generate_env_file
    generate_env_file(
        env_path,
        secret=new_secret,
        github_token=token,
        port=int(env.get("HOOKD_PORT", str(DEFAULT_PORT))),
    )
    print("Updated .env with new secret")

    # Update GitHub webhook
    full_name = env.get("HOOKD_REPO", "")
    if full_name and token:
        hooks = list_webhooks(token, full_name)
        for hook in hooks:
            if "hookd" in hook.get("url", "") or hook.get("url", "").endswith("/webhook"):
                update_webhook_secret(token, full_name, hook["id"], new_secret)
                print(f"Updated GitHub webhook {hook['id']}")

    print("Secret rotated. Restart the service to apply.")


def cmd_disable(args, workdir: Path):
    from hookd.steps.system import detect_service_manager
    from hookd.steps.funnel import disable_funnel

    manager = detect_service_manager()
    if manager == "systemd":
        subprocess.run(["systemctl", "--user", "stop", "hookd"], check=False)
        print("Stopped systemd service")
    elif manager == "launchd":
        subprocess.run(
            ["launchctl", "unload", str(Path.home() / "Library/LaunchAgents/com.hookd.listener.plist")],
            check=False,
        )
        print("Unloaded launchd service")

    if disable_funnel():
        print("Disabled Tailscale Funnel")
    else:
        print("Could not disable funnel (may not be running)")


def cmd_enable(args, workdir: Path):
    from hookd.steps.system import detect_service_manager
    from hookd.steps.funnel import enable_funnel

    env = _load_env(workdir)
    port = _get_port(env)

    manager = detect_service_manager()
    if manager == "systemd":
        subprocess.run(["systemctl", "--user", "start", "hookd"], check=False)
        print("Started systemd service")
    elif manager == "launchd":
        subprocess.run(
            ["launchctl", "load", str(Path.home() / "Library/LaunchAgents/com.hookd.listener.plist")],
            check=False,
        )
        print("Loaded launchd service")

    if enable_funnel(port):
        print(f"Enabled Tailscale Funnel on port {port}")
    else:
        print("Could not enable funnel")


_COMMANDS = {
    "setup": cmd_setup,
    "status": cmd_status,
    "logs": cmd_logs,
    "test": cmd_test,
    "edit": cmd_edit,
    "rotate": cmd_rotate,
    "disable": cmd_disable,
    "enable": cmd_enable,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    workdir = Path.cwd()
    handler = _COMMANDS.get(args.command)
    if handler:
        handler(args, workdir)
    else:
        parser.print_help()
        sys.exit(1)
