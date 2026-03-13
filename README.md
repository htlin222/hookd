# hookd

GitHub webhook listener that runs on your private machine via [Tailscale Funnel](https://tailscale.com/kb/1223/funnel). Features a TUI setup wizard, YAML-based event routing, and shell script handlers with rich environment variables.

## Quick Start

```bash
# Install
uv tool install hookd   # or: pip install hookd

# Run the setup wizard
hookd setup
```

The wizard walks you through: repo detection, dependency checks, GitHub PAT, event selection, secret generation, and deployment (config files, webhook registration, Tailscale Funnel, system service).

## Reusing Across Repos

After the first interactive setup, your GitHub token is saved globally. Use quick setup to configure new repos in seconds:

```bash
cd ~/another-repo
hookd setup --quick                                    # push events on default branch
hookd setup --quick --events push,issues               # multiple event types
hookd setup --quick --branches main,develop            # multiple branches
hookd setup --quick --events push,pull_request --branches main
```

### Global Config (`~/.config/hookd/`)

| File | Purpose |
|------|---------|
| `global.env` | Shared GitHub token (saved automatically during interactive setup) |
| `templates/*.sh` | Reusable handler scripts, copied into each new repo on setup |

To add reusable handler templates:

```bash
mkdir -p ~/.config/hookd/templates
cp my-deploy-script.sh ~/.config/hookd/templates/
# Future setups will auto-copy this into .hookd/handlers/
```

## Architecture

```
GitHub ──webhook──▶ Tailscale Funnel ──▶ hookd listener ──▶ shell handler
                     (HTTPS)              (HTTP localhost)    (bash script)
```

```
hookd/
├── cli.py              # CLI entry point (setup, status, logs, test, edit, rotate, disable, enable)
├── constants.py        # Shared constants
├── global_config.py    # Global config (~/.config/hookd/) for token & templates
├── listener/           # HTTP server core
│   ├── server.py       #   Webhook HTTP server with config hot-reload
│   ├── verify.py       #   HMAC-SHA256 signature verification + replay protection
│   ├── parser.py       #   Payload → environment variable extraction
│   └── dispatcher.py   #   Config-based event routing + handler execution
├── steps/              # Setup wizard logic
│   ├── detect.py       #   Git repo context detection
│   ├── preflight.py    #   Dependency checks (git, tailscale, bash)
│   ├── github.py       #   GitHub webhook CRUD via PyGithub
│   ├── system.py       #   Service management (systemd + launchd)
│   └── funnel.py       #   Tailscale Funnel management
├── templates/          #   Jinja2 templates for config, handlers, services
└── tui/                # Textual TUI wizard
    └── screens/        #   8 wizard screens
```

## Config Reference

The setup wizard generates `.hookd/config.yaml`:

```yaml
events:
  push:
    branches:
      main: handlers/push-main.sh
      staging: handlers/push-staging.sh
  issues:
    opened: handlers/issues-opened.sh
    labeled: handlers/issues-labeled.sh
  issue_comment:
    created: handlers/issue_comment-created.sh
  pull_request:
    opened: handlers/pull_request-opened.sh
  release:
    published: handlers/release-published.sh
```

## Handler Environment Variables

Handlers receive webhook data as environment variables:

| Variable | Events | Description |
|----------|--------|-------------|
| `HOOKD_EVENT` | all | Event type (push, issues, etc.) |
| `HOOKD_ACTION` | all | Event action (opened, created, etc.) |
| `HOOKD_REPO` | all | Repository full name (owner/repo) |
| `HOOKD_SENDER` | all | User who triggered the event |
| `HOOKD_BRANCH` | push | Branch name |
| `HOOKD_PUSHER` | push | Who pushed |
| `HOOKD_COMMIT_COUNT` | push | Number of commits |
| `HOOKD_COMMIT_MESSAGES` | push | Newline-separated commit messages |
| `HOOKD_ISSUE_NUMBER` | issues, issue_comment | Issue number |
| `HOOKD_ISSUE_TITLE` | issues, issue_comment | Issue title |
| `HOOKD_ISSUE_BODY` | issues | Issue body |
| `HOOKD_ISSUE_LABELS` | issues | Comma-separated label names |
| `HOOKD_ISSUE_URL` | issues | Issue HTML URL |
| `HOOKD_COMMENT_BODY` | issue_comment | Comment text |
| `HOOKD_COMMENT_USER` | issue_comment | Commenter login |
| `HOOKD_COMMENT_URL` | issue_comment | Comment HTML URL |
| `HOOKD_RELEASE_TAG` | release | Tag name |
| `HOOKD_RELEASE_NAME` | release | Release title |
| `HOOKD_RELEASE_NOTES` | release | Release body |
| `HOOKD_RELEASE_URL` | release | Release HTML URL |
| `HOOKD_PR_NUMBER` | pull_request | PR number |
| `HOOKD_PR_TITLE` | pull_request | PR title |
| `HOOKD_PR_HEAD` | pull_request | Head branch |
| `HOOKD_PR_BASE` | pull_request | Base branch |

## CLI Commands

| Command | Description |
|---------|-------------|
| `hookd setup` | Launch the TUI setup wizard |
| `hookd setup --quick` | Non-interactive setup using saved token and defaults |
| `hookd status` | Show service and funnel status |
| `hookd logs` | Tail service logs |
| `hookd test [--event push]` | Send a test webhook to local listener |
| `hookd edit` | Open config.yaml in $EDITOR |
| `hookd rotate` | Generate new webhook secret and update GitHub |
| `hookd disable` | Stop service and close funnel |
| `hookd enable` | Start service and open funnel |

## License

MIT
