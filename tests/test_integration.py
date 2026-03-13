import hmac
import hashlib
import json
import time
import threading
import urllib.request
import urllib.error

import pytest

from hookd.listener.server import create_server


def _sign(secret: str, body: bytes) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.fixture
def integration_server(tmp_path):
    secret = "integration-test-secret"

    # Create handler that writes marker file
    handler = tmp_path / "handler.sh"
    handler.write_text(
        '#!/bin/sh\necho "$HOOKD_EVENT:$HOOKD_BRANCH:$HOOKD_SENDER" > '
        + str(tmp_path / "marker.txt")
    )
    handler.chmod(0o755)

    config = {
        "events": {
            "push": {
                "branches": {
                    "main": str(handler),
                }
            },
            "issues": {
                "opened": str(handler),
            },
        }
    }

    srv = create_server(config, secret, 0, tmp_path)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever)
    thread.daemon = True
    thread.start()
    yield srv, port, secret, tmp_path
    srv.shutdown()


def test_full_webhook_delivery(integration_server):
    """Valid push webhook → handler executes → marker file created."""
    srv, port, secret, tmp_path = integration_server

    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "owner/repo", "html_url": "https://github.com/owner/repo"},
        "sender": {"login": "integrationuser"},
        "pusher": {"name": "integrationuser"},
        "commits": [{"message": "integration test", "id": "int123"}],
    }
    body = json.dumps(payload).encode()
    sig = _sign(secret, body)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/webhook",
        data=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "int-delivery-1",
            "Content-Type": "application/json",
        },
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())

    assert data["status"] == "accepted"
    assert data["event"] == "push"
    assert data["handlers"] == [str(tmp_path / "handler.sh")]

    # Handler runs async (fire-and-forget), wait briefly for it to complete
    marker = tmp_path / "marker.txt"
    for _ in range(20):
        if marker.exists():
            break
        time.sleep(0.1)

    assert marker.exists()
    content = marker.read_text().strip()
    assert "push" in content
    assert "main" in content
    assert "integrationuser" in content


def test_replay_rejected(integration_server):
    """Same delivery ID sent twice → second is rejected as duplicate."""
    _, port, secret, _ = integration_server

    payload = {"ref": "refs/heads/main"}
    body = json.dumps(payload).encode()
    sig = _sign(secret, body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "int-replay-1",
        "Content-Type": "application/json",
    }

    req1 = urllib.request.Request(
        f"http://127.0.0.1:{port}/webhook", data=body, headers=headers,
    )
    urllib.request.urlopen(req1)

    req2 = urllib.request.Request(
        f"http://127.0.0.1:{port}/webhook", data=body, headers=headers,
    )
    resp2 = urllib.request.urlopen(req2)
    data = json.loads(resp2.read())
    assert data["status"] == "duplicate"


def test_bad_signature_rejected(integration_server):
    """Invalid HMAC signature → 403."""
    _, port, _, _ = integration_server

    body = json.dumps({"ref": "refs/heads/main"}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/webhook",
        data=body,
        headers={
            "X-Hub-Signature-256": "sha256=0000000000000000000000000000000000000000000000000000000000000000",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "int-bad-sig",
            "Content-Type": "application/json",
        },
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req)
    assert exc_info.value.code == 403


def test_no_handler_for_unmatched_branch(integration_server):
    """Push to non-configured branch → 200 with no_handler status."""
    _, port, secret, _ = integration_server

    payload = {
        "ref": "refs/heads/feature-branch",
        "repository": {"full_name": "owner/repo", "html_url": "https://github.com/owner/repo"},
        "sender": {"login": "user"},
        "pusher": {"name": "user"},
        "commits": [],
    }
    body = json.dumps(payload).encode()
    sig = _sign(secret, body)

    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/webhook",
        data=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "int-no-handler",
            "Content-Type": "application/json",
        },
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    assert data["status"] == "no_handler"


def test_health_endpoint(integration_server):
    """GET /health returns ok."""
    _, port, _, _ = integration_server
    resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/health")
    data = json.loads(resp.read())
    assert data["status"] == "ok"
