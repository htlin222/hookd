from unittest.mock import patch, MagicMock
import json

from hookd.steps.funnel import get_tailscale_hostname, get_funnel_url, enable_funnel, disable_funnel


def test_get_funnel_url():
    url = get_funnel_url("myhost.tail1234.ts.net", 9876)
    assert url == "https://myhost.tail1234.ts.net:9876"


@patch("hookd.steps.funnel.subprocess.run")
def test_get_tailscale_hostname(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"Self": {"DNSName": "myhost.tail1234.ts.net."}}),
    )
    hostname = get_tailscale_hostname()
    assert hostname == "myhost.tail1234.ts.net"


@patch("hookd.steps.funnel.subprocess.run")
def test_get_tailscale_hostname_not_installed(mock_run):
    mock_run.side_effect = FileNotFoundError()
    hostname = get_tailscale_hostname()
    assert hostname is None


@patch("hookd.steps.funnel.subprocess.run")
def test_enable_funnel(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    assert enable_funnel(9876) is True
    mock_run.assert_called_once()


@patch("hookd.steps.funnel.subprocess.run")
def test_disable_funnel(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    assert disable_funnel() is True
