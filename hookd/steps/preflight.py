import json
import shutil
import subprocess
from dataclasses import dataclass, field


@dataclass
class PreflightResult:
    found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return len(self.missing) == 0


@dataclass
class TailscaleStatus:
    logged_in: bool = False
    hostname: str | None = None
    funnel_available: bool = False


def check_dependencies(
    required: list[str] | None = None,
    tunnel: str = "tailscale",
) -> PreflightResult:
    if required is None:
        base = ["git", "bash"]
        if tunnel == "tailscale":
            base.append("tailscale")
        elif tunnel == "cloudflare":
            base.append("cloudflared")
        required = base

    result = PreflightResult()
    for dep in required:
        if shutil.which(dep):
            result.found.append(dep)
        else:
            result.missing.append(dep)
    return result


def check_tailscale() -> TailscaleStatus:
    status = TailscaleStatus()

    try:
        result = subprocess.run(
            ["tailscale", "status", "--self", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            status.logged_in = True
            dns_name = data.get("Self", {}).get("DNSName", "")
            status.hostname = dns_name.rstrip(".") if dns_name else None
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    try:
        result = subprocess.run(
            ["tailscale", "funnel", "status"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            status.funnel_available = True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return status
