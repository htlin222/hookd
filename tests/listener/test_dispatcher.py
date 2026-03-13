import os
import subprocess
import threading
import time

import pytest

from hookd.listener.dispatcher import Dispatcher, worktree


def test_match_push_main(sample_config):
    d = Dispatcher(sample_config)
    handlers = d.find_handlers("push", {"ref": "refs/heads/main"})
    assert handlers == ["handlers/push.sh"]


def test_match_push_staging(sample_config):
    d = Dispatcher(sample_config)
    handlers = d.find_handlers("push", {"ref": "refs/heads/staging"})
    assert handlers == ["handlers/staging.sh"]


def test_push_unmatched_branch(sample_config):
    d = Dispatcher(sample_config)
    handlers = d.find_handlers("push", {"ref": "refs/heads/feature"})
    assert handlers == []


def test_match_issue_opened(sample_config):
    d = Dispatcher(sample_config)
    handlers = d.find_handlers("issues", {"action": "opened"})
    assert handlers == ["handlers/issue-opened.sh"]


def test_match_comment_created(sample_config):
    d = Dispatcher(sample_config)
    handlers = d.find_handlers("issue_comment", {"action": "created"})
    assert handlers == ["handlers/comment.sh"]


def test_unregistered_event(sample_config):
    d = Dispatcher(sample_config)
    handlers = d.find_handlers("release", {"action": "published"})
    assert handlers == []


def test_execute_handler(tmp_path):
    script = tmp_path / "test.sh"
    script.write_text("#!/bin/sh\necho $HOOKD_EVENT")
    script.chmod(0o755)
    d = Dispatcher({"events": {}})
    result = d.execute(str(script), {"HOOKD_EVENT": "push"}, tmp_path)
    assert result.stdout.strip() == "push"
    assert result.returncode == 0


def test_execute_timeout(tmp_path):
    script = tmp_path / "slow.sh"
    script.write_text("#!/bin/sh\nsleep 10")
    script.chmod(0o755)
    d = Dispatcher({"events": {}})
    with pytest.raises(subprocess.TimeoutExpired):
        d.execute(str(script), {}, tmp_path, timeout=1)


def test_execute_async_fires_and_forgets(tmp_path):
    """execute_async runs handler in a background thread."""
    script = tmp_path / "async.sh"
    marker = tmp_path / "async_marker.txt"
    script.write_text(f"#!/bin/sh\necho done > {marker}")
    script.chmod(0o755)

    d = Dispatcher({"events": {}})
    thread = d.execute_async(str(script), {}, tmp_path)
    assert isinstance(thread, threading.Thread)

    thread.join(timeout=5)
    assert marker.exists()
    assert "done" in marker.read_text()


def test_execute_async_callback(tmp_path):
    """execute_async invokes callback with result."""
    script = tmp_path / "cb.sh"
    script.write_text("#!/bin/sh\necho hello")
    script.chmod(0o755)

    results = []
    event = threading.Event()

    def on_done(handler, result_dict):
        results.append(result_dict)
        event.set()

    d = Dispatcher({"events": {}})
    d.execute_async(str(script), {}, tmp_path, callback=on_done)

    event.wait(timeout=5)
    assert len(results) == 1
    assert results[0]["returncode"] == 0
    assert "hello" in results[0]["stdout"]


def test_execute_async_parallel(tmp_path):
    """Multiple async handlers run in parallel, not sequentially."""
    script = tmp_path / "slow.sh"
    # Each handler sleeps 1 second
    script.write_text("#!/bin/sh\nsleep 1\necho done")
    script.chmod(0o755)

    d = Dispatcher({"events": {}})

    start = time.monotonic()
    threads = []
    for _ in range(3):
        t = d.execute_async(str(script), {}, tmp_path)
        threads.append(t)

    for t in threads:
        t.join(timeout=5)

    elapsed = time.monotonic() - start
    # 3 parallel handlers sleeping 1s each should finish in ~1s, not 3s
    assert elapsed < 2.5


# ---------------------------------------------------------------------------
# Worktree tests
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path):
    """Create a minimal git repo for worktree tests."""
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True, env=git_env)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path, capture_output=True, check=True, env=git_env,
    )
    return tmp_path


def test_worktree_creates_and_cleans_up(git_repo):
    """worktree context manager creates a separate dir and removes it."""
    wt_path = None
    with worktree(git_repo) as wt:
        wt_path = wt
        assert wt_path != git_repo
        assert wt_path.exists()
        # It's a valid git worktree
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=wt_path, capture_output=True, text=True,
        )
        assert result.returncode == 0

    # After exiting, worktree should be removed
    assert not wt_path.exists()


def test_worktree_fallback_non_git(tmp_path):
    """worktree yields workdir as-is when not a git repo."""
    with worktree(tmp_path) as wt:
        assert wt == tmp_path


def test_execute_with_worktree(git_repo):
    """execute(use_worktree=True) runs handler in isolated worktree."""
    script = git_repo / "test.sh"
    script.write_text("#!/bin/sh\npwd")
    script.chmod(0o755)

    d = Dispatcher({"events": {}})
    result = d.execute(str(script), {}, git_repo, use_worktree=True)
    assert result.returncode == 0
    # Handler ran in a different directory than git_repo
    handler_cwd = result.stdout.strip()
    assert handler_cwd != str(git_repo)
    assert "hookd-" in handler_cwd


def test_execute_async_uses_worktree(git_repo):
    """execute_async uses worktree by default in git repos."""
    marker = git_repo / "wt_marker.txt"
    script = git_repo / "wt_test.sh"
    # Write the cwd to a marker file at a known location
    script.write_text(f"#!/bin/sh\npwd > {marker}")
    script.chmod(0o755)

    d = Dispatcher({"events": {}})
    thread = d.execute_async(str(script), {}, git_repo)
    thread.join(timeout=10)

    assert marker.exists()
    handler_cwd = marker.read_text().strip()
    assert handler_cwd != str(git_repo)
    assert "hookd-" in handler_cwd


def test_parallel_worktrees_isolated(git_repo):
    """Parallel handlers get separate worktrees."""
    results = []
    lock = threading.Lock()
    done = threading.Event()
    count = [0]

    script = git_repo / "parallel.sh"
    script.write_text("#!/bin/sh\npwd")
    script.chmod(0o755)

    def on_done(handler, result_dict):
        with lock:
            results.append(result_dict)
            count[0] += 1
            if count[0] == 3:
                done.set()

    d = Dispatcher({"events": {}})
    for _ in range(3):
        d.execute_async(str(script), {}, git_repo, callback=on_done)

    done.wait(timeout=15)
    assert len(results) == 3

    # All handlers ran in different directories
    cwds = [r["stdout"].strip() for r in results]
    assert len(set(cwds)) == 3  # all unique
    for cwd in cwds:
        assert cwd != str(git_repo)
