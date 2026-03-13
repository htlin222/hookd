import hmac
import hashlib

import pytest


@pytest.fixture
def webhook_secret():
    return "test-secret-123"


@pytest.fixture
def compute_signature_fn():
    def _compute(secret: str, body: bytes) -> str:
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return f"sha256={sig}"

    return _compute


@pytest.fixture
def sample_push_payload():
    return {
        "ref": "refs/heads/main",
        "repository": {
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
        },
        "sender": {"login": "testuser"},
        "pusher": {"name": "testuser"},
        "commits": [
            {"message": "fix bug", "id": "abc123"},
            {"message": "update readme", "id": "def456"},
        ],
    }


@pytest.fixture
def sample_issue_payload():
    return {
        "action": "opened",
        "issue": {
            "number": 42,
            "title": "Something broke",
            "body": "Please fix",
            "labels": [{"name": "bug"}, {"name": "urgent"}],
            "html_url": "https://github.com/owner/repo/issues/42",
        },
        "repository": {
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
        },
        "sender": {"login": "testuser"},
    }


@pytest.fixture
def sample_comment_payload():
    return {
        "action": "created",
        "comment": {
            "body": "!deploy please",
            "user": {"login": "commenter"},
            "html_url": "https://github.com/owner/repo/issues/42#issuecomment-1",
        },
        "issue": {
            "number": 42,
            "title": "Something broke",
        },
        "repository": {
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
        },
        "sender": {"login": "commenter"},
    }


@pytest.fixture
def sample_config():
    return {
        "events": {
            "push": {
                "branches": {
                    "main": "handlers/push.sh",
                    "staging": "handlers/staging.sh",
                }
            },
            "issues": {
                "opened": "handlers/issue-opened.sh",
                "labeled": "handlers/issue-labeled.sh",
            },
            "issue_comment": {
                "created": "handlers/comment.sh",
            },
        }
    }
