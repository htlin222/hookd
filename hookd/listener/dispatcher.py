import logging
import os
import subprocess
import tempfile
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger("hookd")


def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path, capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@contextmanager
def worktree(workdir: Path):
    """Create a temporary git worktree and clean it up on exit.

    Yields the worktree path. If workdir is not a git repo, yields workdir as-is.
    """
    if not _is_git_repo(workdir):
        yield workdir
        return

    wt_name = f"hookd-{uuid.uuid4().hex[:8]}"
    wt_path = Path(tempfile.gettempdir()) / wt_name

    try:
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(wt_path), "HEAD"],
            cwd=workdir, capture_output=True, text=True, timeout=30, check=True,
        )
        logger.debug("Created worktree %s", wt_path)
        yield wt_path
    except subprocess.CalledProcessError as exc:
        logger.warning("Failed to create worktree, using main workdir: %s", exc.stderr)
        yield workdir
    finally:
        if wt_path.exists():
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(wt_path)],
                    cwd=workdir, capture_output=True, text=True, timeout=30,
                )
                logger.debug("Removed worktree %s", wt_path)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("Could not remove worktree %s", wt_path)


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
        use_worktree: bool = False,
    ) -> subprocess.CompletedProcess:
        if use_worktree:
            with worktree(workdir) as wt_path:
                return self._run_handler(handler, env, wt_path, timeout)
        return self._run_handler(handler, env, workdir, timeout)

    def _run_handler(
        self,
        handler: str,
        env: dict[str, str],
        workdir: Path,
        timeout: int,
    ) -> subprocess.CompletedProcess:
        full_env = {**os.environ, **env, "HOOKD_WORKDIR": str(workdir)}
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

        Each handler runs in its own git worktree for isolation.
        The optional callback receives (handler, result_dict) when done.
        """

        def _run():
            try:
                result = self.execute(
                    handler, env, workdir, use_worktree=True,
                )
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
