import secrets as _secrets

from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Static, Button, Input, RadioButton, RadioSet


class SecretsScreen(Screen):
    DEFAULT_CSS = """
    SecretsScreen { align: center middle; }
    #main { width: 80; max-height: 30; padding: 1 2; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._generated_secret = _secrets.token_hex(32)

    def compose(self):
        with Vertical(id="main"):
            yield Static("Webhook Secret", classes="title")
            yield Static("A secret is used to verify webhook payloads from GitHub.", classes="subtitle")
            yield Static("")

            with RadioSet(id="secret_choice"):
                yield RadioButton("Use generated secret", id="use_generated", value=True)
                yield RadioButton("Enter custom secret", id="use_custom")

            yield Static("")
            yield Static(f"Generated: [bold]{self._generated_secret}[/bold]", id="generated_display")
            yield Input(
                placeholder="Enter your custom secret",
                id="custom_input",
                password=True,
            )
            yield Static("")
            yield Button("Continue", id="continue", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#custom_input", Input).display = False

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        use_custom = event.pressed.id == "use_custom"
        self.query_one("#generated_display", Static).display = not use_custom
        self.query_one("#custom_input", Input).display = use_custom

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            # Determine which secret to use
            radio_set = self.query_one("#secret_choice", RadioSet)
            if radio_set.pressed_index == 1:
                # Custom secret
                secret = self.query_one("#custom_input", Input).value.strip()
                if not secret:
                    return  # Don't continue with empty secret
            else:
                secret = self._generated_secret

            self.app.context["webhook_secret"] = secret

            from hookd.tui.screens.review import ReviewScreen

            self.app.push_screen(ReviewScreen())
