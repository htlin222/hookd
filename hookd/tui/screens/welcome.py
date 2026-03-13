from pathlib import Path

from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Input


class WelcomeScreen(Screen):
    DEFAULT_CSS = """
    WelcomeScreen { align: center middle; }
    #main { width: 80; max-height: 30; padding: 1 2; }
    """

    def compose(self):
        from hookd.steps.detect import detect_git_context

        self._git_ctx = detect_git_context(Path.cwd())

        with Vertical(id="main"):
            yield Static("hookd Setup Wizard", classes="title")
            yield Static("Configure GitHub webhooks via Tailscale Funnel", classes="subtitle")
            yield Static("")

            if self._git_ctx.full_name:
                yield Static(f"Detected repository: [bold]{self._git_ctx.full_name}[/bold]")
                yield Static(f"Branch: {self._git_ctx.branch or 'unknown'}")
                yield Static(f"Remote: {self._git_ctx.remote_url or 'unknown'}")
                yield Static("")
                with Horizontal():
                    yield Button("Continue with this repo", id="continue", variant="primary")
                    yield Button("Enter repo manually", id="manual")
            else:
                yield Static("No Git repository detected in the current directory.")
                yield Static("")
                yield Static("Enter repository details:")
                yield Input(placeholder="owner (e.g. octocat)", id="owner_input")
                yield Input(placeholder="repo (e.g. hello-world)", id="repo_input")
                yield Static("")
                yield Button("Continue", id="manual_continue", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.app.context["owner"] = self._git_ctx.owner
            self.app.context["repo"] = self._git_ctx.repo
            self.app.context["full_name"] = self._git_ctx.full_name
            self.app.context["branch"] = self._git_ctx.branch
            self._push_next()
        elif event.button.id == "manual":
            # Replace content with manual input
            self.query_one("#main").remove_children()
            from textual.containers import Vertical
            from textual.widgets import Static, Input, Button as Btn

            main = self.query_one("#main")
            main.mount(Static("Enter repository details:"))
            main.mount(Input(placeholder="owner (e.g. octocat)", id="owner_input"))
            main.mount(Input(placeholder="repo (e.g. hello-world)", id="repo_input"))
            main.mount(Btn("Continue", id="manual_continue", variant="primary"))
        elif event.button.id == "manual_continue":
            owner_input = self.query_one("#owner_input", Input)
            repo_input = self.query_one("#repo_input", Input)
            owner = owner_input.value.strip()
            repo = repo_input.value.strip()
            if owner and repo:
                self.app.context["owner"] = owner
                self.app.context["repo"] = repo
                self.app.context["full_name"] = f"{owner}/{repo}"
                self.app.context["branch"] = None
                self._push_next()

    def _push_next(self) -> None:
        from hookd.tui.screens.preflight import PreflightScreen

        self.app.push_screen(PreflightScreen())
