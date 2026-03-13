from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button, Checkbox, Input


# Common actions per event type
EVENT_ACTIONS: dict[str, list[str]] = {
    "issues": ["opened", "closed", "edited", "labeled"],
    "issue_comment": ["created", "edited", "deleted"],
    "pull_request": ["opened", "closed", "synchronize", "review_requested"],
    "release": ["published", "created", "released"],
}


class EventsScreen(Screen):
    DEFAULT_CSS = """
    EventsScreen { align: center middle; }
    #main { width: 80; max-height: 40; padding: 1 2; overflow-y: auto; }
    .event-group { margin: 0 0 1 2; }
    """

    def compose(self):
        with Vertical(id="main"):
            yield Static("Webhook Events", classes="title")
            yield Static("Select events to listen for:", classes="subtitle")
            yield Static("")

            # Push event
            yield Checkbox("push", id="evt_push")
            with Vertical(id="push_options", classes="event-group"):
                yield Static("  Branches (comma-separated):")
                yield Input(
                    value=self.app.context.get("branch") or "main",
                    placeholder="main,develop",
                    id="push_branches",
                )

            # Other events with action checkboxes
            for event_name, actions in EVENT_ACTIONS.items():
                yield Checkbox(event_name, id=f"evt_{event_name}")
                with Vertical(id=f"{event_name}_options", classes="event-group"):
                    for action in actions:
                        yield Checkbox(
                            f"  {action}",
                            id=f"act_{event_name}_{action}",
                            value=True,
                        )

            yield Static("")
            yield Button("Continue", id="continue", variant="primary")

    def on_mount(self) -> None:
        # Hide action groups initially
        self.query_one("#push_options").display = False
        for event_name in EVENT_ACTIONS:
            self.query_one(f"#{event_name}_options").display = False

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb_id = event.checkbox.id or ""
        if cb_id == "evt_push":
            self.query_one("#push_options").display = event.value
        elif cb_id.startswith("evt_"):
            event_name = cb_id.removeprefix("evt_")
            if event_name in EVENT_ACTIONS:
                self.query_one(f"#{event_name}_options").display = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self._save_and_continue()

    def _save_and_continue(self) -> None:
        events_config: list[dict] = []

        # Handle push
        push_cb = self.query_one("#evt_push", Checkbox)
        if push_cb.value:
            branches_raw = self.query_one("#push_branches", Input).value.strip()
            branches = [b.strip() for b in branches_raw.split(",") if b.strip()]
            branch_handlers = {}
            for branch in branches:
                branch_handlers[branch] = f"handlers/push-{branch}.sh"
            events_config.append({
                "name": "push",
                "branches": branch_handlers,
            })

        # Handle other events
        for event_name, actions in EVENT_ACTIONS.items():
            evt_cb = self.query_one(f"#evt_{event_name}", Checkbox)
            if evt_cb.value:
                action_handlers = {}
                for action in actions:
                    act_cb = self.query_one(f"#act_{event_name}_{action}", Checkbox)
                    if act_cb.value:
                        action_handlers[action] = f"handlers/{event_name}-{action}.sh"
                if action_handlers:
                    events_config.append({
                        "name": event_name,
                        "actions": action_handlers,
                    })

        self.app.context["events_config"] = events_config

        from hookd.tui.screens.secrets import SecretsScreen

        self.app.push_screen(SecretsScreen())
