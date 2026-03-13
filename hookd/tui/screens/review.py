from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button

from hookd.constants import DEFAULT_PORT


class ReviewScreen(Screen):
    DEFAULT_CSS = """
    ReviewScreen { align: center middle; }
    #main { width: 80; max-height: 40; padding: 1 2; overflow-y: auto; }
    """

    def compose(self):
        ctx = self.app.context
        port = ctx.get("port", DEFAULT_PORT)
        secret = ctx.get("webhook_secret", "")
        masked_secret = secret[:4] + "..." + secret[-4:] if len(secret) > 8 else "****"

        with Vertical(id="main"):
            yield Static("Review Configuration", classes="title")
            yield Static("")

            # Repository
            yield Static(f"[bold]Repository:[/bold] {ctx.get('full_name', 'N/A')}")
            yield Static(f"[bold]GitHub User:[/bold] {ctx.get('github_user', 'N/A')}")
            yield Static(f"[bold]Port:[/bold] {port}")
            yield Static(f"[bold]Secret:[/bold] {masked_secret}")
            yield Static("")

            # Events
            events_config = ctx.get("events_config", [])
            yield Static("[bold]Events:[/bold]")
            for evt in events_config:
                name = evt["name"]
                if name == "push":
                    branches = evt.get("branches", {})
                    for branch, handler in branches.items():
                        yield Static(f"  push ({branch}) -> {handler}")
                else:
                    actions = evt.get("actions", {})
                    for action, handler in actions.items():
                        yield Static(f"  {name}.{action} -> {handler}")

            yield Static("")

            # Files to be created
            yield Static("[bold]Files to create:[/bold]")
            yield Static("  .hookd/config.yaml")
            yield Static("  .hookd/.env")
            for evt in events_config:
                if evt["name"] == "push":
                    for handler in evt.get("branches", {}).values():
                        yield Static(f"  .hookd/{handler}")
                else:
                    for handler in evt.get("actions", {}).values():
                        yield Static(f"  .hookd/{handler}")

            yield Static("")
            with Horizontal():
                yield Button("Back", id="back")
                yield Button("Deploy", id="deploy", variant="success")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "deploy":
            from hookd.tui.screens.deploy import DeployScreen

            self.app.push_screen(DeployScreen())
