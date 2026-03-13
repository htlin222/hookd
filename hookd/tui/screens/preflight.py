from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button


class PreflightScreen(Screen):
    DEFAULT_CSS = """
    PreflightScreen { align: center middle; }
    #main { width: 80; max-height: 30; padding: 1 2; }
    """

    REQUIRED_DEPS = ["git", "bash"]

    def compose(self):
        with Vertical(id="main"):
            yield Static("Preflight Checks", classes="title")
            yield Static("")
            yield Static("Checking dependencies...", id="dep_status")
            yield Static("", id="dep_list")
            yield Static("", id="ts_status")
            yield Static("")
            yield Button("Continue", id="continue", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self._run_checks()

    def _run_checks(self) -> None:
        from hookd.steps.preflight import check_dependencies, check_tailscale

        deps = check_dependencies()
        ts = check_tailscale()

        lines = []
        for dep in deps.found:
            lines.append(f"  [green]\u2713[/green] {dep}")
        for dep in deps.missing:
            lines.append(f"  [red]\u2717[/red] {dep}")

        self.query_one("#dep_status", Static).update("Dependencies:")
        self.query_one("#dep_list", Static).update("\n".join(lines))

        ts_lines = []
        if ts.logged_in:
            ts_lines.append(f"  [green]\u2713[/green] Tailscale logged in")
            if ts.hostname:
                ts_lines.append(f"    Hostname: {ts.hostname}")
                self.app.context["ts_hostname"] = ts.hostname
        else:
            ts_lines.append(f"  [yellow]![/yellow] Tailscale not logged in")

        if ts.funnel_available:
            ts_lines.append(f"  [green]\u2713[/green] Funnel available")
            self.app.context["funnel_available"] = True
        else:
            ts_lines.append(f"  [yellow]![/yellow] Funnel not available (can configure later)")
            self.app.context["funnel_available"] = False

        self.query_one("#ts_status", Static).update("\n".join(ts_lines))

        # Enable continue if required deps are present
        required_ok = all(d in deps.found for d in self.REQUIRED_DEPS)
        self.query_one("#continue", Button).disabled = not required_ok

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            from hookd.tui.screens.github import GitHubScreen

            self.app.push_screen(GitHubScreen())
