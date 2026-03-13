import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from functools import partial

from hookd.constants import SIGNATURE_HEADER, EVENT_HEADER, DELIVERY_HEADER
from hookd.listener.verify import verify_signature, DeliveryTracker
from hookd.listener.parser import payload_to_env
from hookd.listener.dispatcher import Dispatcher

logger = logging.getLogger("hookd")


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


def create_server(
    config: dict,
    secret: str,
    port: int,
    workdir: Path,
) -> HTTPServer:
    server = HTTPServer(("", port), WebhookHandler)
    server.webhook_secret = secret
    server.tracker = DeliveryTracker()
    server.dispatcher = Dispatcher(config)
    server.workdir = workdir
    return server
