import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

from hookd.constants import HOOKD_DIR, CONFIG_FILE, ENV_FILE, EVENTS_FILE, DEFAULT_PORT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hookd",
        description="GitHub webhook listener via Tailscale Funnel",
    )
    sub = parser.add_subparsers(dest="command")

    setup_parser = sub.add_parser("setup", help="Launch the setup wizard")
    setup_parser.add_argument(
        "--quick", "-q", action="store_true",
        help="Non-interactive setup using defaults and saved global token",
    )
    setup_parser.add_argument(
        "--events", default="push",
        help="Comma-separated event types for quick setup (default: push)",
    )
    setup_parser.add_argument(
        "--branches", default=None,
        help="Comma-separated branches for push events (default: repo default branch or main)",
    )

    sub.add_parser("status", help="Show service and funnel status")

    logs_parser = sub.add_parser("logs", help="Tail service logs")
    logs_parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Output raw JSON lines",
    )
    logs_parser.add_argument(
        "-n", type=int, default=20,
        help="Number of recent events to show (default: 20)",
    )

    sub.add_parser("list", help="List GitHub webhooks for the repository")

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

    uninstall_parser = sub.add_parser("uninstall", help="Remove hookd completely")
    uninstall_parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt",
    )

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
    if getattr(args, "quick", False):
        _quick_setup(args, workdir)
        return

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


def _quick_setup(args, workdir: Path):
    """Non-interactive setup using saved global token and sensible defaults."""
    import secrets as secrets_mod

    from hookd.steps.detect import detect_git_context
    from hookd.global_config import get_global_token, copy_global_templates
    from hookd.templates import render_template
    from hookd.steps.system import generate_env_file

    # 1. Detect repo
    git_ctx = detect_git_context(workdir)
    if not git_ctx.full_name:
        print("Error: No Git repository detected. Run from a Git repo with a GitHub remote.")
        sys.exit(1)
    print(f"Repository: {git_ctx.full_name}")

    # 2. Resolve token
    token = get_global_token()
    if not token:
        print("Error: No saved GitHub token found.")
        print("Run 'hookd setup' (interactive) first to save a token,")
        print("or manually save one with: mkdir -p ~/.config/hookd && echo 'HOOKD_GITHUB_TOKEN=ghp_...' > ~/.config/hookd/global.env")
        sys.exit(1)

    # Validate token
    from hookd.steps.github import validate_token
    username = validate_token(token)
    if not username:
        print("Error: Saved global token is invalid. Run 'hookd setup' to update it.")
        sys.exit(1)
    print(f"GitHub user: {username}")

    # 3. Build events config
    branch = args.branches or git_ctx.branch or "main"
    branches = [b.strip() for b in branch.split(",") if b.strip()]
    event_names = [e.strip() for e in args.events.split(",") if e.strip()]

    events_config = []
    for evt_name in event_names:
        if evt_name == "push":
            branch_handlers = {b: f"handlers/push-{b}.sh" for b in branches}
            events_config.append({"name": "push", "branches": branch_handlers})
        else:
            # Default actions per event type
            from hookd.tui.screens.events import EVENT_ACTIONS
            actions = EVENT_ACTIONS.get(evt_name, ["opened"])
            action_handlers = {a: f"handlers/{evt_name}-{a}.sh" for a in actions}
            events_config.append({"name": evt_name, "actions": action_handlers})

    # 4. Generate secret
    secret = secrets_mod.token_hex(32)
    port = DEFAULT_PORT

    # 5. Create .hookd directory
    hookd_dir = workdir / HOOKD_DIR
    hookd_dir.mkdir(parents=True, exist_ok=True)
    (hookd_dir / "handlers").mkdir(exist_ok=True)
    print("Created .hookd/")

    # 6. Write config.yaml
    config_content = render_template("config.yaml.j2", events=events_config)
    (hookd_dir / CONFIG_FILE).write_text(config_content)
    print("Written config.yaml")

    # 7. Create handler scripts
    for evt in events_config:
        name = evt["name"]
        if name == "push":
            for b, handler_path in evt["branches"].items():
                content = render_template(
                    "handler.sh.j2",
                    handler_name=f"push-{b}",
                    event_type="push",
                    handler_body=f'echo "[hookd] Push to {b}"',
                )
                fpath = hookd_dir / handler_path
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content)
                fpath.chmod(0o755)
                print(f"Created {handler_path}")
        else:
            for action, handler_path in evt["actions"].items():
                content = render_template(
                    "handler.sh.j2",
                    handler_name=f"{name}-{action}",
                    event_type=name,
                    handler_body=f'echo "[hookd] {name} {action}"',
                )
                fpath = hookd_dir / handler_path
                fpath.parent.mkdir(parents=True, exist_ok=True)
                fpath.write_text(content)
                fpath.chmod(0o755)
                print(f"Created {handler_path}")

    # 7b. Copy global templates
    copied = copy_global_templates(hookd_dir / "handlers")
    if copied:
        print(f"Copied {len(copied)} global template(s): {', '.join(copied)}")

    # 8. Write .env
    generate_env_file(
        path=hookd_dir / ".env",
        secret=secret,
        github_token=token,
        port=port,
        repo=git_ctx.full_name,
    )
    print("Written .env")

    # 9. Register webhook on GitHub
    try:
        from hookd.steps.github import create_webhook
        from hookd.steps.funnel import get_tailscale_hostname, get_funnel_url

        hostname = get_tailscale_hostname()
        if hostname:
            funnel_url = get_funnel_url(hostname, port)
        else:
            funnel_url = f"https://localhost:{port}"

        create_webhook(
            token=token,
            full_name=git_ctx.full_name,
            url=funnel_url,
            secret=secret,
            events=[e["name"] for e in events_config],
        )
        print(f"Webhook registered at {funnel_url}")
    except Exception as exc:
        print(f"Warning: Could not register webhook: {exc}")
        print("You can register it manually later.")

    # 10. Install system service
    try:
        from hookd.steps.system import detect_service_manager, generate_service_file, install_service

        manager = detect_service_manager()
        if manager:
            content = generate_service_file(manager=manager, workdir=str(workdir), port=port)
            svc_path = install_service(manager, content, str(workdir))
            print(f"Service installed: {svc_path}")
    except Exception as exc:
        print(f"Warning: Could not install service: {exc}")

    print()
    print("Quick setup complete!")
    print(f"  Repository: {git_ctx.full_name}")
    print(f"  Events: {', '.join(event_names)}")
    print(f"  Port: {port}")
    print()
    print("Next steps:")
    print("  hookd enable    Start the service and funnel")
    print("  hookd test      Send a test webhook")
    print("  hookd edit      Customize your config")


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
    from hookd.listener.server import EventLog

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
        # Show recent events from events.jsonl
        events_path = workdir / HOOKD_DIR / EVENTS_FILE
        if not events_path.exists():
            print("No event log found. Run the listener to generate events.")
            return

        event_log = EventLog(events_path)
        entries = event_log.read(n=args.n)

        if not entries:
            print("No events recorded yet.")
            return

        if args.json_output:
            for entry in entries:
                print(json.dumps(entry))
        else:
            for entry in entries:
                ts = entry.get("timestamp", "")
                event = entry.get("event", "")
                action = entry.get("action", "")
                repo = entry.get("repo", "")
                sender = entry.get("sender", "")
                handlers = entry.get("handlers", [])
                label = f"{event}"
                if action:
                    label += f".{action}"
                print(f"[{ts}] {label}  repo={repo}  sender={sender}  handlers={len(handlers)}")


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


def cmd_list(args, workdir: Path):
    from hookd.steps.github import list_webhooks

    env = _load_env(workdir)
    token = env.get("HOOKD_GITHUB_TOKEN", "")
    repo = env.get("HOOKD_REPO", "")

    if not token:
        print("Error: No HOOKD_GITHUB_TOKEN found in .hookd/.env")
        print("Run 'hookd setup' first or add HOOKD_GITHUB_TOKEN to .hookd/.env")
        sys.exit(1)

    if not repo:
        print("Error: No HOOKD_REPO found in .hookd/.env")
        print("Add HOOKD_REPO=owner/repo to .hookd/.env")
        sys.exit(1)

    try:
        hooks = list_webhooks(token, repo)
    except Exception as e:
        print(f"Error fetching webhooks: {e}")
        sys.exit(1)

    if not hooks:
        print(f"No webhooks found for {repo}")
        return

    print(f"Webhooks for {repo}:")
    print()
    for hook in hooks:
        status = "active" if hook["active"] else "inactive"
        events = ", ".join(hook["events"])
        print(f"  ID:     {hook['id']}")
        print(f"  URL:    {hook['url']}")
        print(f"  Events: {events}")
        print(f"  Status: {status}")
        print()


def cmd_uninstall(args, workdir: Path):
    from hookd.steps.system import detect_service_manager
    from hookd.steps.funnel import disable_funnel

    hookd_dir = workdir / HOOKD_DIR
    env = _load_env(workdir)
    token = env.get("HOOKD_GITHUB_TOKEN", "")
    repo = env.get("HOOKD_REPO", "")
    manager = detect_service_manager()

    # Print what will be removed
    print("hookd uninstall will remove:")
    if manager:
        print(f"  - {manager} service for hookd")
    print("  - Tailscale Funnel configuration")
    if token and repo:
        print(f"  - GitHub webhooks for {repo}")
    if hookd_dir.exists():
        print(f"  - {hookd_dir} directory")
    print()

    if not args.yes:
        answer = input("Continue? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    removed = []

    # Step 1: Stop service
    if manager == "systemd":
        subprocess.run(["systemctl", "--user", "stop", "hookd"], check=False)
        subprocess.run(["systemctl", "--user", "disable", "hookd"], check=False)
        service_path = Path.home() / ".config" / "systemd" / "user" / "hookd.service"
        if service_path.exists():
            subprocess.run(["rip", str(service_path)], check=False)
            removed.append(f"systemd service ({service_path})")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    elif manager == "launchd":
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.hookd.listener.plist"
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            check=False,
        )
        if plist_path.exists():
            subprocess.run(["rip", str(plist_path)], check=False)
            removed.append(f"launchd service ({plist_path})")

    # Step 2: Disable funnel
    if disable_funnel():
        removed.append("Tailscale Funnel")

    # Step 3: Delete GitHub webhook
    if token and repo:
        try:
            from hookd.steps.github import list_webhooks, delete_webhook

            hooks = list_webhooks(token, repo)
            for hook in hooks:
                url = hook.get("url", "")
                if "hookd" in url or url.endswith("/webhook"):
                    delete_webhook(token, repo, hook["id"])
                    removed.append(f"GitHub webhook {hook['id']}")
        except Exception as e:
            print(f"Warning: Could not remove GitHub webhooks: {e}")

    # Step 4: Remove .hookd directory
    if hookd_dir.exists():
        subprocess.run(["rip", str(hookd_dir)], check=False)
        removed.append(f"{hookd_dir} directory")

    # Summary
    print()
    if removed:
        print("Removed:")
        for item in removed:
            print(f"  - {item}")
    else:
        print("Nothing was removed.")
    print()
    print("hookd has been uninstalled.")


_COMMANDS = {
    "setup": cmd_setup,
    "status": cmd_status,
    "logs": cmd_logs,
    "test": cmd_test,
    "edit": cmd_edit,
    "rotate": cmd_rotate,
    "disable": cmd_disable,
    "enable": cmd_enable,
    "list": cmd_list,
    "uninstall": cmd_uninstall,
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
