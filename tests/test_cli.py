import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from hookd.cli import build_parser, _load_env, _get_port, cmd_test
from hookd.constants import DEFAULT_PORT


def test_parser_setup():
    parser = build_parser()
    args = parser.parse_args(["setup"])
    assert args.command == "setup"


def test_parser_status():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_parser_logs():
    parser = build_parser()
    args = parser.parse_args(["logs"])
    assert args.command == "logs"


def test_parser_test_event():
    parser = build_parser()
    args = parser.parse_args(["test", "--event", "push"])
    assert args.event == "push"


def test_parser_test_default_event():
    parser = build_parser()
    args = parser.parse_args(["test"])
    assert args.event == "push"


def test_parser_edit():
    parser = build_parser()
    args = parser.parse_args(["edit"])
    assert args.command == "edit"


def test_parser_rotate():
    parser = build_parser()
    args = parser.parse_args(["rotate"])
    assert args.command == "rotate"


def test_parser_disable():
    parser = build_parser()
    args = parser.parse_args(["disable"])
    assert args.command == "disable"


def test_parser_enable():
    parser = build_parser()
    args = parser.parse_args(["enable"])
    assert args.command == "enable"


def test_parser_no_command():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.command is None


def test_parser_list():
    parser = build_parser()
    args = parser.parse_args(["list"])
    assert args.command == "list"


def test_parser_uninstall():
    parser = build_parser()
    args = parser.parse_args(["uninstall"])
    assert args.command == "uninstall"
    assert args.yes is False


def test_parser_uninstall_yes():
    parser = build_parser()
    args = parser.parse_args(["uninstall", "--yes"])
    assert args.command == "uninstall"
    assert args.yes is True


# ---------------------------------------------------------------------------
# _load_env tests
# ---------------------------------------------------------------------------

def test_load_env(tmp_path):
    """_load_env parses a .env file into a dict."""
    hookd_dir = tmp_path / ".hookd"
    hookd_dir.mkdir()
    env_file = hookd_dir / ".env"
    env_file.write_text(
        "HOOKD_SECRET=mysecret\n"
        "HOOKD_PORT=8080\n"
        "# comment line\n"
        "\n"
        "HOOKD_GITHUB_TOKEN=ghp_abc123\n"
    )
    result = _load_env(tmp_path)
    assert result["HOOKD_SECRET"] == "mysecret"
    assert result["HOOKD_PORT"] == "8080"
    assert result["HOOKD_GITHUB_TOKEN"] == "ghp_abc123"
    assert "#" not in "".join(result.keys())


def test_load_env_missing(tmp_path):
    """_load_env returns empty dict when .env file does not exist."""
    result = _load_env(tmp_path)
    assert result == {}


# ---------------------------------------------------------------------------
# _get_port tests
# ---------------------------------------------------------------------------

def test_get_port_from_env():
    """_get_port extracts port from env dict."""
    env = {"HOOKD_PORT": "4321"}
    assert _get_port(env) == 4321


def test_get_port_default():
    """_get_port returns DEFAULT_PORT when not specified."""
    assert _get_port({}) == DEFAULT_PORT


def test_get_port_from_args_overrides_env():
    """_get_port prefers args_port over env."""
    env = {"HOOKD_PORT": "4321"}
    assert _get_port(env, args_port=5555) == 5555


# ---------------------------------------------------------------------------
# cmd_test tests
# ---------------------------------------------------------------------------

def test_cmd_test_sends_webhook(tmp_path):
    """cmd_test constructs and sends correct webhook request."""
    hookd_dir = tmp_path / ".hookd"
    hookd_dir.mkdir()
    env_file = hookd_dir / ".env"
    env_file.write_text("HOOKD_SECRET=testsecret123\nHOOKD_PORT=9999\n")

    args = SimpleNamespace(event="push", port=None)

    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"status": "ok"}).encode()
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=fake_resp) as mock_urlopen:
        cmd_test(args, tmp_path)

        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://127.0.0.1:9999/webhook"
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("X-github-event") == "push"
        assert req.get_header("X-hub-signature-256").startswith("sha256=")
        # Verify payload contains expected push data
        body = json.loads(req.data)
        assert body["ref"] == "refs/heads/main"
        assert body["sender"]["login"] == "hookd-test"


def test_cmd_test_no_secret(tmp_path):
    """cmd_test exits when no HOOKD_SECRET is found."""
    hookd_dir = tmp_path / ".hookd"
    hookd_dir.mkdir()
    env_file = hookd_dir / ".env"
    env_file.write_text("HOOKD_PORT=9999\n")

    args = SimpleNamespace(event="push", port=None)

    with pytest.raises(SystemExit) as exc_info:
        cmd_test(args, tmp_path)
    assert exc_info.value.code == 1


def test_cmd_test_non_push_event(tmp_path):
    """cmd_test uses generic payload for non-push events."""
    hookd_dir = tmp_path / ".hookd"
    hookd_dir.mkdir()
    env_file = hookd_dir / ".env"
    env_file.write_text("HOOKD_SECRET=testsecret123\nHOOKD_PORT=9999\n")

    args = SimpleNamespace(event="issues", port=None)

    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"status": "ok"}).encode()
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=fake_resp) as mock_urlopen:
        cmd_test(args, tmp_path)

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-github-event") == "issues"
        body = json.loads(req.data)
        assert body["action"] == "opened"
        assert "commits" not in body
