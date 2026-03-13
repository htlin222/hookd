from pathlib import Path

from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button, RichLog
from textual.worker import Worker, WorkerState

from hookd.constants import HOOKD_DIR, CONFIG_FILE, DEFAULT_PORT


class DeployScreen(Screen):
    DEFAULT_CSS = """
    DeployScreen { align: center middle; }
    #main { width: 80; max-height: 40; padding: 1 2; }
    RichLog { height: 20; border: solid $primary; }
    """

    def compose(self):
        with Vertical(id="main"):
            yield Static("Deploying...", classes="title", id="deploy_title")
            yield Static("")
            yield RichLog(id="log", highlight=True, markup=True)
            yield Static("")
            yield Button("Finish", id="finish", variant="success", disabled=True)

    def on_mount(self) -> None:
        self._run_deploy()

    def _run_deploy(self) -> None:
        self.run_worker(self._deploy_steps, exclusive=True)

    async def _deploy_steps(self) -> None:
        log = self.query_one("#log", RichLog)
        ctx = self.app.context
        port = ctx.get("port", DEFAULT_PORT)
        workdir = Path.cwd()
        hookd_dir = workdir / HOOKD_DIR

        # Step 1: Create .hookd directory
        log.write("[bold]Step 1:[/bold] Creating .hookd directory...")
        try:
            hookd_dir.mkdir(parents=True, exist_ok=True)
            (hookd_dir / "handlers").mkdir(exist_ok=True)
            log.write("  [green]\u2713[/green] Directory created")
        except Exception as exc:
            log.write(f"  [red]\u2717 Error: {exc}[/red]")
            return

        # Step 2: Render and write config.yaml
        log.write("[bold]Step 2:[/bold] Writing config.yaml...")
        try:
            from hookd.templates import render_template

            config_content = render_template(
                "config.yaml.j2",
                events=ctx.get("events_config", []),
            )
            (hookd_dir / CONFIG_FILE).write_text(config_content)
            log.write("  [green]\u2713[/green] config.yaml written")
        except Exception as exc:
            log.write(f"  [red]\u2717 Error: {exc}[/red]")
            return

        # Step 3: Create handler scripts
        log.write("[bold]Step 3:[/bold] Creating handler scripts...")
        try:
            from hookd.templates import render_template

            events_config = ctx.get("events_config", [])
            for evt in events_config:
                name = evt["name"]
                if name == "push":
                    for branch, handler_path in evt.get("branches", {}).items():
                        content = render_template(
                            "handler.sh.j2",
                            handler_name=f"push-{branch}",
                            event_type="push",
                            handler_body=f'echo "[hookd] Push to {branch}"',
                        )
                        fpath = hookd_dir / handler_path
                        fpath.parent.mkdir(parents=True, exist_ok=True)
                        fpath.write_text(content)
                        fpath.chmod(0o755)
                        log.write(f"  [green]\u2713[/green] {handler_path}")
                else:
                    for action, handler_path in evt.get("actions", {}).items():
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
                        log.write(f"  [green]\u2713[/green] {handler_path}")
        except Exception as exc:
            log.write(f"  [red]\u2717 Error: {exc}[/red]")
            return

        # Step 4: Write .env file
        log.write("[bold]Step 4:[/bold] Writing .env file...")
        try:
            from hookd.steps.system import generate_env_file

            generate_env_file(
                path=hookd_dir / ".env",
                secret=ctx.get("webhook_secret", ""),
                github_token=ctx.get("github_token", ""),
                port=port,
            )
            log.write("  [green]\u2713[/green] .env written")
        except Exception as exc:
            log.write(f"  [red]\u2717 Error: {exc}[/red]")
            return

        # Step 5: Register webhook on GitHub
        log.write("[bold]Step 5:[/bold] Registering webhook on GitHub...")
        try:
            from hookd.steps.github import create_webhook
            from hookd.steps.funnel import get_funnel_url

            hostname = ctx.get("ts_hostname")
            if hostname:
                funnel_url = get_funnel_url(hostname, port)
            else:
                funnel_url = f"https://localhost:{port}"

            ctx["funnel_url"] = funnel_url

            event_names = [e["name"] for e in ctx.get("events_config", [])]
            create_webhook(
                token=ctx.get("github_token", ""),
                full_name=ctx.get("full_name", ""),
                url=funnel_url,
                secret=ctx.get("webhook_secret", ""),
                events=event_names,
            )
            log.write(f"  [green]\u2713[/green] Webhook registered at {funnel_url}")
        except Exception as exc:
            log.write(f"  [yellow]! Warning: {exc}[/yellow]")
            log.write("  You can register the webhook manually later.")

        # Step 6: Enable Tailscale Funnel
        log.write("[bold]Step 6:[/bold] Enabling Tailscale Funnel...")
        if ctx.get("funnel_available"):
            try:
                from hookd.steps.funnel import enable_funnel

                success = enable_funnel(port)
                if success:
                    log.write("  [green]\u2713[/green] Funnel enabled")
                else:
                    log.write("  [yellow]! Funnel could not be enabled[/yellow]")
            except Exception as exc:
                log.write(f"  [yellow]! Warning: {exc}[/yellow]")
        else:
            log.write("  [dim]Skipped (Tailscale Funnel not available)[/dim]")

        # Step 7: Install system service
        log.write("[bold]Step 7:[/bold] Installing system service...")
        try:
            from hookd.steps.system import detect_service_manager, generate_service_file, install_service

            manager = detect_service_manager()
            if manager:
                content = generate_service_file(
                    manager=manager,
                    workdir=str(workdir),
                    port=port,
                )
                svc_path = install_service(manager, content, str(workdir))
                log.write(f"  [green]\u2713[/green] Service installed: {svc_path}")
                ctx["service_manager"] = manager
                ctx["service_path"] = str(svc_path)
            else:
                log.write("  [dim]Skipped (no supported service manager found)[/dim]")
        except Exception as exc:
            log.write(f"  [yellow]! Warning: {exc}[/yellow]")

        log.write("")
        log.write("[bold green]Deployment complete![/bold green]")

        self.query_one("#deploy_title", Static).update("Deployment Complete")
        self.query_one("#finish", Button).disabled = False

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            log = self.query_one("#log", RichLog)
            log.write(f"[red]Worker error: {event.worker.error}[/red]")
            self.query_one("#finish", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "finish":
            from hookd.tui.screens.done import DoneScreen

            self.app.push_screen(DoneScreen())
