import re
import subprocess
from pathlib import Path
from dataclasses import dataclass

_GITHUB_RE = re.compile(r"github\.com[:/](.+)/(.+?)(?:\.git)?$")


@dataclass
class GitContext:
    owner: str | None = None
    repo: str | None = None
    branch: str | None = None
    remote_url: str | None = None

    @property
    def full_name(self) -> str | None:
        if self.owner and self.repo:
            return f"{self.owner}/{self.repo}"
        return None


def detect_git_context(path: Path | str) -> GitContext:
    path = Path(path)
    ctx = GitContext()

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            ctx.remote_url = url
            match = _GITHUB_RE.search(url)
            if match:
                ctx.owner = match.group(1)
                ctx.repo = match.group(2)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            ctx.branch = result.stdout.strip() or None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return ctx
