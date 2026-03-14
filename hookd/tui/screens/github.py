from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button, Input, Checkbox


class GitHubScreen(Screen):
    DEFAULT_CSS = """
    GitHubScreen { align: center middle; }
    #main { width: 80; max-height: 30; padding: 1 2; }
    """

    def compose(self):
        from hookd.global_config import get_global_token

        self._global_token = get_global_token()

        with Vertical(id="main"):
            yield Static("GitHub Authentication", classes="title")
            yield Static("")
            yield Static("Enter your GitHub Personal Access Token (PAT).")
            yield Static("Required scopes: repo, admin:repo_hook", classes="subtitle")
            yield Static("")

            if self._global_token:
                masked = self._global_token[:4] + "..." + self._global_token[-4:]
                yield Static(
                    f"[green]Found saved token:[/green] {masked}",
                    id="global_token_hint",
                )

            yield Input(
                placeholder="ghp_...",
                id="token_input",
                password=True,
                value=self._global_token or "",
            )
            yield Static("")
            yield Checkbox("Save token globally for future repos", id="save_global", value=True)
            yield Static("")
            yield Static("", id="status")
            yield Button("Validate Token", id="validate", variant="primary")
            yield Button("Continue", id="continue", variant="success", disabled=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "validate":
            self._validate_token()
        elif event.button.id == "continue":
            # Save globally if checked
            save_cb = self.query_one("#save_global", Checkbox)
            if save_cb.value and self.app.context.get("github_token"):
                from hookd.global_config import save_global_token

                save_global_token(self.app.context["github_token"])

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
