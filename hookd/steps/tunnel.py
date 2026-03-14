"""Tunnel provider abstraction.

Supports multiple backends for exposing the local webhook listener:
- tailscale: Tailscale Funnel (default, stable URL, free)
- cloudflare: Cloudflare Tunnel via cloudflared (free, production-ready)
- none: No tunnel; user handles exposure (reverse proxy, ngrok, etc.)
"""

import json
import logging
import shutil
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger("hookd")


class TunnelProvider(ABC):
    """Base class for tunnel providers."""

    name: str = "base"

    @abstractmethod
    def get_public_url(self, port: int) -> str | None:
        """Return the public URL for the given port, or None if unavailable."""

    @abstractmethod
    def enable(self, port: int) -> bool:
        """Start exposing the port. Returns True on success."""

    @abstractmethod
    def disable(self) -> bool:
        """Stop exposing. Returns True on success."""

    @abstractmethod
    def status(self) -> dict:
        """Return status information as a dict."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this tunnel provider's dependencies are installed."""


class TailscaleTunnel(TunnelProvider):
    """Tunnel via Tailscale Funnel."""

    name = "tailscale"

    def get_public_url(self, port: int) -> str | None:
        hostname = self._get_hostname()
        if hostname:
            return f"https://{hostname}:{port}"
        return None

    def enable(self, port: int) -> bool:
        try:
            result = subprocess.run(
                ["tailscale", "funnel", str(port)],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def disable(self) -> bool:
        try:
            result = subprocess.run(
                ["tailscale", "funnel", "off"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def status(self) -> dict:
        try:
            result = subprocess.run(
                ["tailscale", "funnel", "status", "--json"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass
        return {}

    def is_available(self) -> bool:
        return shutil.which("tailscale") is not None

    def _get_hostname(self) -> str | None:
        try:
            result = subprocess.run(
                ["tailscale", "status", "--self", "--json"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                dns_name = data.get("Self", {}).get("DNSName", "")
                return dns_name.rstrip(".") if dns_name else None
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            return None


class CloudflareTunnel(TunnelProvider):
    """Tunnel via Cloudflare Tunnel (cloudflared).

    Requires cloudflared to be installed and authenticated.
    Uses `cloudflared tunnel --url` for quick tunnels.
    """

    name = "cloudflare"

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._url: str | None = None

    def get_public_url(self, port: int) -> str | None:
        return self._url

    def enable(self, port: int) -> bool:
        if self._process and self._process.poll() is None:
            return True  # already running

        try:
            self._process = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # cloudflared prints the URL to stderr
            import re
            for line in iter(self._process.stderr.readline, ""):
                match = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", line)
                if match:
                    self._url = match.group(1)
                    logger.info("Cloudflare tunnel URL: %s", self._url)
                    return True
                # Stop reading after enough lines to avoid blocking forever
                if "failed" in line.lower() or "error" in line.lower():
                    logger.error("cloudflared error: %s", line.strip())
                    self._process.terminate()
                    self._process = None
                    return False
        except FileNotFoundError:
            logger.error("cloudflared not found. Install it from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
            return False
        return False

    def disable(self) -> bool:
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            self._url = None
            return True
        return True

    def status(self) -> dict:
        running = self._process is not None and self._process.poll() is None
        return {
            "running": running,
            "url": self._url,
        }

    def is_available(self) -> bool:
        return shutil.which("cloudflared") is not None


class NoTunnel(TunnelProvider):
    """No tunnel; the user handles public exposure themselves."""

    name = "none"

    def get_public_url(self, port: int) -> str | None:
        return f"http://localhost:{port}"

    def enable(self, port: int) -> bool:
        return True

    def disable(self) -> bool:
        return True

    def status(self) -> dict:
        return {"tunnel": "none", "note": "No tunnel configured. Expose the port yourself."}

    def is_available(self) -> bool:
        return True


# Registry of available providers
TUNNEL_PROVIDERS: dict[str, type[TunnelProvider]] = {
    "tailscale": TailscaleTunnel,
    "cloudflare": CloudflareTunnel,
    "none": NoTunnel,
}


def get_tunnel_provider(name: str) -> TunnelProvider:
    """Create a tunnel provider by name.

    Raises ValueError if the name is unknown.
    """
    cls = TUNNEL_PROVIDERS.get(name)
    if cls is None:
        valid = ", ".join(TUNNEL_PROVIDERS.keys())
        raise ValueError(f"Unknown tunnel provider: {name!r}. Valid options: {valid}")
    return cls()
