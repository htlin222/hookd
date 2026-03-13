from hookd.listener.parser import payload_to_env


def test_push_env(sample_push_payload):
    env = payload_to_env("push", sample_push_payload)
    assert env["HOOKD_EVENT"] == "push"
    assert env["HOOKD_REPO"] == "owner/repo"
    assert env["HOOKD_SENDER"] == "testuser"
    assert env["HOOKD_BRANCH"] == "main"
    assert env["HOOKD_PUSHER"] == "testuser"
    assert env["HOOKD_COMMIT_COUNT"] == "2"
    assert "fix bug" in env["HOOKD_COMMIT_MESSAGES"]


def test_issue_env(sample_issue_payload):
    env = payload_to_env("issues", sample_issue_payload)
    assert env["HOOKD_EVENT"] == "issues"
    assert env["HOOKD_ACTION"] == "opened"
    assert env["HOOKD_ISSUE_NUMBER"] == "42"
    assert env["HOOKD_ISSUE_TITLE"] == "Something broke"
    assert env["HOOKD_ISSUE_LABELS"] == "bug,urgent"
    assert "issues/42" in env["HOOKD_ISSUE_URL"]


def test_comment_env(sample_comment_payload):
    env = payload_to_env("issue_comment", sample_comment_payload)
    assert env["HOOKD_COMMENT_BODY"] == "!deploy please"
    assert env["HOOKD_COMMENT_USER"] == "commenter"
    assert env["HOOKD_ISSUE_NUMBER"] == "42"


def test_release_env():
    payload = {
        "action": "published",
        "release": {
            "tag_name": "v1.0.0",
            "name": "Release 1.0",
            "body": "First release",
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
        },
        "repository": {
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
        },
        "sender": {"login": "releaser"},
    }
    env = payload_to_env("release", payload)
    assert env["HOOKD_RELEASE_TAG"] == "v1.0.0"
    assert env["HOOKD_RELEASE_NAME"] == "Release 1.0"
    assert env["HOOKD_RELEASE_NOTES"] == "First release"
    assert "releases/tag/v1.0.0" in env["HOOKD_RELEASE_URL"]
