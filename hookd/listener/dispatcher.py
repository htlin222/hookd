import logging
import os
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger("hookd")


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

    def execute_async(
        self,
        handler: str,
        env: dict[str, str],
        workdir: Path,
        callback=None,
    ) -> threading.Thread:
        """Fire-and-forget handler execution in a background thread.

        The optional callback receives (handler, result_dict) when done.
        """

        def _run():
            try:
                result = self.execute(handler, env, workdir)
                result_dict = {
                    "handler": handler,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
                logger.info("Handler %s exited with %d", handler, result.returncode)
                if result.returncode != 0:
                    logger.warning(
                        "Handler %s stderr: %s", handler, result.stderr[:500]
                    )
            except subprocess.TimeoutExpired:
                result_dict = {"handler": handler, "error": "timeout"}
                logger.error("Handler %s timed out", handler)
            except Exception as exc:
                result_dict = {"handler": handler, "error": str(exc)}
                logger.error("Handler %s failed: %s", handler, exc)

            if callback:
                try:
                    callback(handler, result_dict)
                except Exception as exc:
                    logger.error("Callback error for %s: %s", handler, exc)

        thread = threading.Thread(target=_run, name=f"hookd-{handler}", daemon=True)
        thread.start()
        return thread
