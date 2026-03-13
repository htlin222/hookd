import os
import subprocess
from pathlib import Path


class Dispatcher:
    def __init__(self, config: dict):
        self._events = config.get("events", {})

    def find_handlers(self, event: str, payload: dict) -> list[str]:
        event_config = self._events.get(event)
        if event_config is None:
            return []
        if event == "push":
            return self._match_push(event_config, payload)
        return self._match_action(event_config, payload)

    def _match_push(self, config: dict, payload: dict) -> list[str]:
        branches = config.get("branches", {})
        ref = payload.get("ref", "")
        branch = ref.removeprefix("refs/heads/")
        handler = branches.get(branch)
        return [handler] if handler else []

    def _match_action(self, config: dict, payload: dict) -> list[str]:
        action = payload.get("action", "")
        handler = config.get(action)
        return [handler] if handler else []

    def execute(
        self,
        handler: str,
        env: dict[str, str],
        workdir: Path,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        full_env = {**os.environ, **env}
        return subprocess.run(
            ["bash", handler],
            cwd=workdir,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
