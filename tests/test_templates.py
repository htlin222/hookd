from hookd.templates import render_template


def test_render_config():
    events = [{"name": "push", "branches": {"main": "handlers/push.sh"}}]
    result = render_template("config.yaml.j2", events=events)
    assert "push:" in result
    assert "main: handlers/push.sh" in result


def test_render_config_action_event():
    events = [{"name": "issues", "actions": {"opened": "handlers/issue-opened.sh"}}]
    result = render_template("config.yaml.j2", events=events)
    assert "issues:" in result
    assert "opened: handlers/issue-opened.sh" in result


def test_render_handler():
    result = render_template(
        "handler.sh.j2",
        handler_name="deploy",
        event_type="push",
        handler_body="git pull",
    )
    assert "#!/usr/bin/env bash" in result
    assert "set -euo pipefail" in result
    assert "git pull" in result
    assert "deploy" in result


def test_render_systemd_service():
    result = render_template(
        "hookd.service.j2",
        workdir="/opt/hookd",
        python_path="/usr/bin/python3",
        port=9876,
    )
    assert "ExecStart=" in result
    assert "/opt/hookd" in result


def test_render_launchd_plist():
    result = render_template(
        "hookd.plist.j2",
        workdir="/opt/hookd",
        python_path="/usr/bin/python3",
        port=9876,
    )
    assert "<plist" in result
    assert "hookd" in result
