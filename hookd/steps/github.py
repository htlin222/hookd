from github import Github, GithubException


def validate_token(token: str) -> str | None:
    try:
        g = Github(token)
        user = g.get_user()
        return user.login
    except GithubException:
        return None


def get_repo(token: str, full_name: str):
    g = Github(token)
    return g.get_repo(full_name)


def create_webhook(
    token: str,
    full_name: str,
    url: str,
    secret: str,
    events: list[str],
):
    repo = get_repo(token, full_name)
    config = {"url": url, "content_type": "json", "secret": secret}
    return repo.create_hook("web", config, events=events, active=True)


def list_webhooks(token: str, full_name: str) -> list[dict]:
    repo = get_repo(token, full_name)
    hooks = []
    for hook in repo.get_hooks():
        hooks.append({
            "id": hook.id,
            "url": hook.config.get("url", ""),
            "events": hook.events,
            "active": hook.active,
        })
    return hooks


def delete_webhook(token: str, full_name: str, hook_id: int):
    repo = get_repo(token, full_name)
    hook = repo.get_hook(hook_id)
    hook.delete()


def update_webhook_secret(
    token: str,
    full_name: str,
    hook_id: int,
    new_secret: str,
):
    repo = get_repo(token, full_name)
    hook = repo.get_hook(hook_id)
    hook.edit("web", config={**hook.config, "secret": new_secret})
