import subprocess
import threading
import time

import pytest

from hookd.listener.dispatcher import Dispatcher


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
