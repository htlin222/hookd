def payload_to_env(event: str, payload: dict) -> dict[str, str]:
    import json
    env: dict[str, str] = {
        "HOOKD_EVENT": event,
        "HOOKD_ACTION": str(payload.get("action", "")),
        "HOOKD_REPO": payload.get("repository", {}).get("full_name", ""),
        "HOOKD_SENDER": payload.get("sender", {}).get("login", ""),
        "HOOKD_PAYLOAD_JSON": json.dumps(payload),
    }

    extractors = {
        "push": _extract_push,
        "issues": _extract_issues,
        "issue_comment": _extract_comment,
        "release": _extract_release,
        "pull_request": _extract_pull_request,
    }

    extractor = extractors.get(event)
    if extractor:
        env.update(extractor(payload))

    return env


def _extract_push(payload: dict) -> dict[str, str]:
    ref = payload.get("ref", "")
    branch = ref.removeprefix("refs/heads/")
    commits = payload.get("commits", [])
    messages = "\n".join(c.get("message", "") for c in commits)
    return {
        "HOOKD_BRANCH": branch,
        "HOOKD_PUSHER": payload.get("pusher", {}).get("name", ""),
        "HOOKD_COMMIT_COUNT": str(len(commits)),
        "HOOKD_COMMIT_MESSAGES": messages,
    }


def _extract_issues(payload: dict) -> dict[str, str]:
    issue = payload.get("issue", {})
    labels = ",".join(l.get("name", "") for l in issue.get("labels", []))
    return {
        "HOOKD_ISSUE_NUMBER": str(issue.get("number", "")),
        "HOOKD_ISSUE_TITLE": issue.get("title", ""),
        "HOOKD_ISSUE_BODY": issue.get("body", ""),
        "HOOKD_ISSUE_LABELS": labels,
        "HOOKD_ISSUE_URL": issue.get("html_url", ""),
    }


def _extract_comment(payload: dict) -> dict[str, str]:
    comment = payload.get("comment", {})
    issue = payload.get("issue", {})
    return {
        "HOOKD_COMMENT_BODY": comment.get("body", ""),
        "HOOKD_COMMENT_USER": comment.get("user", {}).get("login", ""),
        "HOOKD_COMMENT_URL": comment.get("html_url", ""),
        "HOOKD_ISSUE_NUMBER": str(issue.get("number", "")),
        "HOOKD_ISSUE_TITLE": issue.get("title", ""),
    }


def _extract_release(payload: dict) -> dict[str, str]:
    release = payload.get("release", {})
    return {
        "HOOKD_RELEASE_TAG": release.get("tag_name", ""),
        "HOOKD_RELEASE_NAME": release.get("name", ""),
        "HOOKD_RELEASE_NOTES": release.get("body", ""),
        "HOOKD_RELEASE_URL": release.get("html_url", ""),
    }


def _extract_pull_request(payload: dict) -> dict[str, str]:
    pr = payload.get("pull_request", {})
    labels = ",".join(l.get("name", "") for l in pr.get("labels", []))
    return {
        "HOOKD_PR_NUMBER": str(pr.get("number", "")),
        "HOOKD_PR_TITLE": pr.get("title", ""),
        "HOOKD_PR_BODY": pr.get("body", ""),
        "HOOKD_PR_URL": pr.get("html_url", ""),
        "HOOKD_PR_LABELS": labels,
        "HOOKD_PR_HEAD": pr.get("head", {}).get("ref", ""),
        "HOOKD_PR_BASE": pr.get("base", {}).get("ref", ""),
    }
