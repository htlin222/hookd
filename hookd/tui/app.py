from textual.app import App
from textual.binding import Binding


class HookdApp(App):
    TITLE = "hookd"
    CSS = """
    Screen { align: center middle; }
    #main { width: 80; max-height: 40; }
    .title { text-align: center; text-style: bold; }
    .subtitle { text-align: center; color: $text-muted; }
    .success { color: $success; }
    .error { color: $error; }
    .warning { color: $warning; }
    Button { margin: 1 2; }
    """
    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(self, context: dict | None = None):
        super().__init__()
        self.context = context or {}

    def on_mount(self) -> None:
        from hookd.tui.screens.welcome import WelcomeScreen

        self.push_screen(WelcomeScreen())
