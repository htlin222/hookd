from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button, Input


class GitHubScreen(Screen):
    DEFAULT_CSS = """
    GitHubScreen { align: center middle; }
    #main { width: 80; max-height: 30; padding: 1 2; }
    """

    def compose(self):
        with Vertical(id="main"):
            yield Static("GitHub Authentication", classes="title")
            yield Static("")
            yield Static("Enter your GitHub Personal Access Token (PAT).")
            yield Static("Required scopes: repo, admin:repo_hook", classes="subtitle")
            yield Static("")
            yield Input(placeholder="ghp_...", id="token_input", password=True)
            yield Static("")
            yield Static("", id="status")
            yield Button("Validate Token", id="validate", variant="primary")
            yield Button("Continue", id="continue", variant="success", disabled=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "validate":
            self._validate_token()
        elif event.button.id == "continue":
            from hookd.tui.screens.events import EventsScreen

            self.app.push_screen(EventsScreen())

    def _validate_token(self) -> None:
        token = self.query_one("#token_input", Input).value.strip()
        status = self.query_one("#status", Static)

        if not token:
            status.update("[red]Please enter a token[/red]")
            return

        status.update("Validating...")
        try:
            from hookd.steps.github import validate_token

            username = validate_token(token)
            if username:
                status.update(f"[green]\u2713 Authenticated as {username}[/green]")
                self.app.context["github_token"] = token
                self.app.context["github_user"] = username
                self.query_one("#continue", Button).disabled = False
            else:
                status.update("[red]\u2717 Invalid token[/red]")
                self.query_one("#continue", Button).disabled = True
        except Exception as exc:
            status.update(f"[red]\u2717 Error: {exc}[/red]")
            self.query_one("#continue", Button).disabled = True
