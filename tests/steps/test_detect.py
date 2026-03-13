import subprocess

from hookd.steps.detect import detect_git_context, GitContext


def test_detect_ssh_url(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:owner/repo.git"],
        cwd=tmp_path, capture_output=True,
    )
    ctx = detect_git_context(tmp_path)
    assert ctx.owner == "owner"
    assert ctx.repo == "repo"
    assert ctx.remote_url == "git@github.com:owner/repo.git"
    assert ctx.full_name == "owner/repo"


def test_detect_https_url(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/myorg/myrepo.git"],
        cwd=tmp_path, capture_output=True,
    )
    ctx = detect_git_context(tmp_path)
    assert ctx.owner == "myorg"
    assert ctx.repo == "myrepo"
    assert ctx.full_name == "myorg/myrepo"


def test_detect_https_no_git_suffix(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/myorg/myrepo"],
        cwd=tmp_path, capture_output=True,
    )
    ctx = detect_git_context(tmp_path)
    assert ctx.owner == "myorg"
    assert ctx.repo == "myrepo"


def test_detect_no_git_repo(tmp_path):
    ctx = detect_git_context(tmp_path)
    assert ctx.owner is None
    assert ctx.repo is None
    assert ctx.remote_url is None
    assert ctx.full_name is None


def test_detect_branch(tmp_path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)
    ctx = detect_git_context(tmp_path)
    assert ctx.branch == "main"
