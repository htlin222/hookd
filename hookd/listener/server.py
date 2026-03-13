import json
import logging
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import yaml

from hookd.constants import SIGNATURE_HEADER, EVENT_HEADER, DELIVERY_HEADER
from hookd.listener.verify import verify_signature, DeliveryTracker
from hookd.listener.parser import payload_to_env
from hookd.listener.dispatcher import Dispatcher

logger = logging.getLogger("hookd")


class EventLog:
    """Append-only structured event log using JSON Lines format."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        event: str,
        action: str,
        repo: str,
        sender: str,
        delivery_id: str,
        handlers: list[str],
        results: list[dict],
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "action": action,
            "repo": repo,
            "sender": sender,
            "delivery_id": delivery_id,
            "handlers": handlers,
            "results": results,
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def read(self, n: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text().splitlines()
        entries = []
        for line in lines[-n:]:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries


class WebhookHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(405, {"error": "Method not allowed"})

    def do_POST(self):
        if self.path != "/webhook":
            self._respond(404, {"error": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        signature = self.headers.get(SIGNATURE_HEADER, "")
        if not verify_signature(body, signature, self.server.webhook_secret):
            logger.warning("Invalid signature from %s", self.client_address)
            self._respond(403, {"error": "Invalid signature"})
            return

        delivery_id = self.headers.get(DELIVERY_HEADER, "")
        if delivery_id and not self.server.tracker.check_and_record(delivery_id):
            logger.info("Replay rejected: %s", delivery_id)
            self._respond(200, {"status": "duplicate", "delivery_id": delivery_id})
            return

        event = self.headers.get(EVENT_HEADER, "")
        if not event:
            self._respond(400, {"error": "Missing event header"})
            return

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON"})
            return

        self.server.maybe_reload_config()

        env = payload_to_env(event, payload)
        handlers = self.server.dispatcher.find_handlers(event, payload)

        if not handlers:
            logger.info("No handlers for %s", event)
            self._respond(200, {"status": "no_handler", "event": event})
            return

        results = []
        for handler in handlers:
            try:
                result = self.server.dispatcher.execute(
                    handler, env, self.server.workdir
                )
                results.append({
                    "handler": handler,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                })
                logger.info(
                    "Handler %s exited with %d", handler, result.returncode
                )
            except Exception as exc:
                results.append({
                    "handler": handler,
                    "error": str(exc),
                })
                logger.error("Handler %s failed: %s", handler, exc)

        # Log event to structured event log
        if self.server.event_log:
            action = payload.get("action", "")
            repo = payload.get("repository", {}).get("full_name", "")
            sender_login = payload.get("sender", {}).get("login", "")
            self.server.event_log.write(
                event=event,
                action=action,
                repo=repo,
                sender=sender_login,
                delivery_id=delivery_id,
                handlers=[h for h in handlers],
                results=results,
            )

        self._respond(200, {"status": "ok", "event": event, "results": results})

    def _respond(self, code: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        logger.debug(format, *args)


class HookdServer(HTTPServer):
    def __init__(
        self,
        port: int,
        config: dict,
        secret: str,
        workdir: Path,
        config_path: Path | None = None,
        event_log_path: Path | None = None,
    ):
        super().__init__(("", port), WebhookHandler)
        self.webhook_secret = secret
        self.tracker = DeliveryTracker()
        self.dispatcher = Dispatcher(config)
        self.workdir = workdir
        self.config_path = config_path
        self.event_log = EventLog(event_log_path) if event_log_path else None
        self._config_mtime: float = 0.0
        if config_path and config_path.exists():
            self._config_mtime = config_path.stat().st_mtime

    def maybe_reload_config(self):
        if not self.config_path or not self.config_path.exists():
            return
        try:
            mtime = self.config_path.stat().st_mtime
            if mtime > self._config_mtime:
                with open(self.config_path) as f:
                    config = yaml.safe_load(f) or {}
                self.dispatcher = Dispatcher(config)
                self._config_mtime = mtime
                logger.info("Config reloaded from %s", self.config_path)
        except Exception as exc:
            logger.error("Failed to reload config: %s", exc)


def create_server(
    config: dict,
    secret: str,
    port: int,
    workdir: Path,
    config_path: Path | None = None,
    event_log_path: Path | None = None,
) -> HookdServer:
    return HookdServer(port, config, secret, workdir, config_path, event_log_path)
