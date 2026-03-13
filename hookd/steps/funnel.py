import json
import subprocess


def get_tailscale_hostname() -> str | None:
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


def get_funnel_url(hostname: str, port: int) -> str:
    return f"https://{hostname}:{port}"


def enable_funnel(port: int) -> bool:
    try:
        result = subprocess.run(
            ["tailscale", "funnel", str(port)],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def disable_funnel() -> bool:
    try:
        result = subprocess.run(
            ["tailscale", "funnel", "off"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_funnel_status() -> dict:
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
