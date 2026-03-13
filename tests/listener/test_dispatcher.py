import subprocess

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
