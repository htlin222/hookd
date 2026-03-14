from unittest.mock import patch, MagicMock
import json

import pytest

from hookd.steps.tunnel import (
    TailscaleTunnel,
    CloudflareTunnel,
    NoTunnel,
    get_tunnel_provider,
    TUNNEL_PROVIDERS,
)


# ---------------------------------------------------------------------------
# NoTunnel tests
# ---------------------------------------------------------------------------

def test_no_tunnel_always_available():
    t = NoTunnel()
    assert t.is_available() is True


def test_no_tunnel_enable_disable():
    t = NoTunnel()
    assert t.enable(9876) is True
    assert t.disable() is True


def test_no_tunnel_url():
    t = NoTunnel()
    assert t.get_public_url(9876) == "http://localhost:9876"


def test_no_tunnel_status():
    t = NoTunnel()
    assert t.status()["tunnel"] == "none"


# ---------------------------------------------------------------------------
# TailscaleTunnel tests
# ---------------------------------------------------------------------------

@patch("hookd.steps.tunnel.subprocess.run")
def test_tailscale_get_public_url(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"Self": {"DNSName": "myhost.tail1234.ts.net."}}),
    )
    t = TailscaleTunnel()
    url = t.get_public_url(9876)
    assert url == "https://myhost.tail1234.ts.net:9876"


@patch("hookd.steps.tunnel.subprocess.run")
def test_tailscale_get_public_url_not_available(mock_run):
    mock_run.side_effect = FileNotFoundError()
    t = TailscaleTunnel()
    assert t.get_public_url(9876) is None


@patch("hookd.steps.tunnel.subprocess.run")
def test_tailscale_enable(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    t = TailscaleTunnel()
    assert t.enable(9876) is True


@patch("hookd.steps.tunnel.subprocess.run")
def test_tailscale_disable(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    t = TailscaleTunnel()
    assert t.disable() is True


@patch("hookd.steps.tunnel.shutil.which")
def test_tailscale_is_available(mock_which):
    mock_which.return_value = "/usr/bin/tailscale"
    t = TailscaleTunnel()
    assert t.is_available() is True

    mock_which.return_value = None
    assert t.is_available() is False


@patch("hookd.steps.tunnel.subprocess.run")
def test_tailscale_status_json(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"AllowFunnel": {"myhost:443": True}}),
    )
    t = TailscaleTunnel()
    status = t.status()
    assert "AllowFunnel" in status


# ---------------------------------------------------------------------------
# CloudflareTunnel tests
# ---------------------------------------------------------------------------

@patch("hookd.steps.tunnel.shutil.which")
def test_cloudflare_is_available(mock_which):
    mock_which.return_value = "/usr/bin/cloudflared"
    t = CloudflareTunnel()
    assert t.is_available() is True

    mock_which.return_value = None
    assert t.is_available() is False


def test_cloudflare_url_before_enable():
    t = CloudflareTunnel()
    assert t.get_public_url(9876) is None


def test_cloudflare_disable_when_not_running():
    t = CloudflareTunnel()
    assert t.disable() is True


def test_cloudflare_status_not_running():
    t = CloudflareTunnel()
    status = t.status()
    assert status["running"] is False
    assert status["url"] is None


# ---------------------------------------------------------------------------
# get_tunnel_provider tests
# ---------------------------------------------------------------------------

def test_get_tunnel_provider_valid():
    for name in TUNNEL_PROVIDERS:
        provider = get_tunnel_provider(name)
        assert provider.name == name


def test_get_tunnel_provider_invalid():
    with pytest.raises(ValueError, match="Unknown tunnel provider"):
        get_tunnel_provider("ngrok")
