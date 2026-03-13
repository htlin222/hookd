from unittest.mock import MagicMock, patch

from hookd.steps.github import validate_token, create_webhook, list_webhooks, delete_webhook


@patch("hookd.steps.github.Github")
def test_validate_token_success(mock_github_cls):
    mock_user = MagicMock()
    mock_user.login = "testuser"
    mock_github_cls.return_value.get_user.return_value = mock_user

    result = validate_token("ghp_test")
    assert result == "testuser"


@patch("hookd.steps.github.Github")
def test_validate_token_failure(mock_github_cls):
    from github import GithubException
    mock_github_cls.return_value.get_user.side_effect = GithubException(401, "Bad credentials", None)

    result = validate_token("ghp_bad")
    assert result is None


@patch("hookd.steps.github.get_repo")
def test_create_webhook(mock_get_repo):
    mock_repo = MagicMock()
    mock_hook = MagicMock()
    mock_repo.create_hook.return_value = mock_hook
    mock_get_repo.return_value = mock_repo

    result = create_webhook("token", "owner/repo", "https://example.com/webhook", "secret", ["push"])
    assert result == mock_hook
    mock_repo.create_hook.assert_called_once_with(
        "web",
        {"url": "https://example.com/webhook", "content_type": "json", "secret": "secret"},
        events=["push"],
        active=True,
    )


@patch("hookd.steps.github.get_repo")
def test_list_webhooks(mock_get_repo):
    mock_hook = MagicMock()
    mock_hook.id = 123
    mock_hook.config = {"url": "https://example.com/webhook"}
    mock_hook.events = ["push"]
    mock_hook.active = True
    mock_repo = MagicMock()
    mock_repo.get_hooks.return_value = [mock_hook]
    mock_get_repo.return_value = mock_repo

    hooks = list_webhooks("token", "owner/repo")
    assert len(hooks) == 1
    assert hooks[0]["id"] == 123
    assert hooks[0]["url"] == "https://example.com/webhook"


@patch("hookd.steps.github.get_repo")
def test_delete_webhook(mock_get_repo):
    mock_hook = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_hook.return_value = mock_hook
    mock_get_repo.return_value = mock_repo

    delete_webhook("token", "owner/repo", 123)
    mock_repo.get_hook.assert_called_once_with(123)
    mock_hook.delete.assert_called_once()
