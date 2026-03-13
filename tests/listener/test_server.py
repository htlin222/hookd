import hmac
import hashlib
import json
import threading
import urllib.request

import pytest

from hookd.listener.server import create_server


@pytest.fixture
def server_and_url(tmp_path, webhook_secret, sample_config):
    # Create a handler script that writes a marker file
    handlers_dir = tmp_path / "handlers"
    handlers_dir.mkdir()
    handler = handlers_dir / "push.sh"
    handler.write_text(
        '#!/bin/sh\necho "$HOOKD_EVENT:$HOOKD_BRANCH" > '
        + str(tmp_path / "marker.txt")
    )
    handler.chmod(0o755)

    config = {
        "events": {
            "push": {
                "branches": {
                    "main": str(handler),
                }
            }
        }
    }

    srv = create_server(config, webhook_secret, 0, tmp_path)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever)
    thread.daemon = True
    thread.start()
    yield srv, f"http://127.0.0.1:{port}", tmp_path
    srv.shutdown()


def _sign(secret: str, body: bytes) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def test_get_returns_405(server_and_url):
    _, url, _ = server_and_url
    req = urllib.request.Request(f"{url}/webhook", method="GET")
    try:
        urllib.request.urlopen(req)
        pytest.fail("Expected 405")
    except urllib.error.HTTPError as e:
        assert e.code == 405


def test_health_endpoint(server_and_url):
    _, url, _ = server_and_url
    resp = urllib.request.urlopen(f"{url}/health")
    data = json.loads(resp.read())
    assert data["status"] == "ok"


def test_bad_signature_returns_403(server_and_url):
    _, url, _ = server_and_url
    body = json.dumps({"ref": "refs/heads/main"}).encode()
    req = urllib.request.Request(
        f"{url}/webhook",
        data=body,
        headers={
            "X-Hub-Signature-256": "sha256=bad",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "d-bad",
            "Content-Type": "application/json",
        },
    )
    try:
        urllib.request.urlopen(req)
        pytest.fail("Expected 403")
    except urllib.error.HTTPError as e:
        assert e.code == 403


def test_valid_webhook_executes_handler(server_and_url, webhook_secret):
    srv, url, tmp_path = server_and_url
    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "owner/repo", "html_url": "https://github.com/owner/repo"},
        "sender": {"login": "testuser"},
        "pusher": {"name": "testuser"},
        "commits": [{"message": "test", "id": "abc"}],
    }
    body = json.dumps(payload).encode()
    sig = _sign(webhook_secret, body)

    req = urllib.request.Request(
        f"{url}/webhook",
        data=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "d-valid-1",
            "Content-Type": "application/json",
        },
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    assert data["status"] == "ok"
    assert data["event"] == "push"

    marker = tmp_path / "marker.txt"
    assert marker.exists()
    assert "push:main" in marker.read_text()


def test_replay_rejected(server_and_url, webhook_secret):
    _, url, _ = server_and_url
    payload = {"ref": "refs/heads/main"}
    body = json.dumps(payload).encode()
    sig = _sign(webhook_secret, body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "d-replay-1",
        "Content-Type": "application/json",
    }

    # First request
    req = urllib.request.Request(f"{url}/webhook", data=body, headers=headers)
    urllib.request.urlopen(req)

    # Replay — same delivery ID
    req2 = urllib.request.Request(f"{url}/webhook", data=body, headers=headers)
    resp2 = urllib.request.urlopen(req2)
    data = json.loads(resp2.read())
    assert data["status"] == "duplicate"
