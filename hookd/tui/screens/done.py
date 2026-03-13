from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button

from hookd.constants import DEFAULT_PORT


class DoneScreen(Screen):
    DEFAULT_CSS = """
    DoneScreen { align: center middle; }
    #main { width: 80; max-height: 30; padding: 1 2; }
    """

    def compose(self):
        ctx = self.app.context
        port = ctx.get("port", DEFAULT_PORT)
        funnel_url = ctx.get("funnel_url", f"https://localhost:{port}")

        with Vertical(id="main"):
            yield Static("[bold green]Setup Complete![/bold green]", classes="title")
            yield Static("")
            yield Static(f"[bold]Webhook URL:[/bold] {funnel_url}")
            yield Static(f"[bold]Repository:[/bold] {ctx.get('full_name', 'N/A')}")
            yield Static("")
            yield Static("[bold]Helpful commands:[/bold]")
            yield Static("  hookd listen          Start the webhook listener")
            yield Static("  hookd status          Check service and funnel status")
            yield Static("  hookd logs            View recent webhook deliveries")
            yield Static("  hookd test            Send a test ping event")
            yield Static("  hookd webhooks list   List registered webhooks")
            yield Static("")

            manager = ctx.get("service_manager")
            if manager == "systemd":
                yield Static("[bold]Service commands:[/bold]")
                yield Static("  systemctl --user start hookd")
                yield Static("  systemctl --user status hookd")
                yield Static("  journalctl --user -u hookd -f")
                yield Static("")
            elif manager == "launchd":
                yield Static("[bold]Service commands:[/bold]")
                yield Static("  launchctl load ~/Library/LaunchAgents/com.hookd.listener.plist")
                yield Static("  launchctl list | grep hookd")
                yield Static("")

            yield Button("Finish", id="finish", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "finish":
            self.app.exit()
