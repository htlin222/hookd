"""Tests for hookd TUI screens."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest

from hookd.tui.app import HookdApp
from textual.widgets import Static, Button, Input, Checkbox, RadioButton, RadioSet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakeGitContext:
    owner: str | None = None
    repo: str | None = None
    branch: str | None = None
    remote_url: str | None = None

    @property
    def full_name(self) -> str | None:
        if self.owner and self.repo:
            return f"{self.owner}/{self.repo}"
        return None


@dataclass
class _FakePreflightResult:
    found: list[str]
    missing: list[str]

    @property
    def all_ok(self) -> bool:
        return len(self.missing) == 0


@dataclass
class _FakeTailscaleStatus:
    logged_in: bool = False
    hostname: str | None = None
    funnel_available: bool = False


def _get_static_text(widget: Static) -> str:
    """Extract text content from a Static widget (works across Textual versions)."""
    # Textual v3+ uses name-mangled __content
    for attr in ("renderable", "_renderable"):
        if hasattr(widget, attr):
            return str(getattr(widget, attr))
    # Name-mangled private attr
    content = getattr(widget, "_Static__content", None)
    if content is not None:
        return str(content)
    return ""


def _make_app(**ctx_overrides) -> HookdApp:
    ctx = {"workdir": "/tmp"}
    ctx.update(ctx_overrides)
    return HookdApp(context=ctx)


# ---------------------------------------------------------------------------
# WelcomeScreen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_welcome_screen_no_git_context():
    """WelcomeScreen shows manual input fields when no git context is detected."""
    fake_ctx = _FakeGitContext()  # no owner/repo => full_name is None

    with patch("hookd.steps.detect.detect_git_context", return_value=fake_ctx):
        app = _make_app()
        async with app.run_test() as pilot:
            # The title should be present
            statics = app.screen.query(Static)
            texts = [_get_static_text(s) for s in statics]
            title_found = any("hookd Setup Wizard" in t for t in texts)
            assert title_found, "Expected title 'hookd Setup Wizard'"

            # Manual input fields should be present
            owner_input = app.screen.query_one("#owner_input", Input)
            repo_input = app.screen.query_one("#repo_input", Input)
            assert owner_input is not None
            assert repo_input is not None

            # Continue button for manual entry
            btn = app.screen.query_one("#manual_continue", Button)
            assert btn is not None


@pytest.mark.asyncio
async def test_welcome_screen_with_git_context():
    """WelcomeScreen shows detected repo info when git context is available."""
    fake_ctx = _FakeGitContext(
        owner="octocat",
        repo="hello-world",
        branch="main",
        remote_url="https://github.com/octocat/hello-world.git",
    )

    with patch("hookd.steps.detect.detect_git_context", return_value=fake_ctx):
        app = _make_app()
        async with app.run_test() as pilot:
            statics = app.screen.query(Static)
            texts = [_get_static_text(s) for s in statics]
            # Should show detected repo
            assert any("octocat/hello-world" in t for t in texts), (
                f"Expected repo info in statics, got: {texts}"
            )
            # Continue button should exist
            btn = app.screen.query_one("#continue", Button)
            assert btn is not None


@pytest.mark.asyncio
async def test_welcome_screen_renders_title():
    """WelcomeScreen always renders the title."""
    fake_ctx = _FakeGitContext()
    with patch("hookd.steps.detect.detect_git_context", return_value=fake_ctx):
        app = _make_app()
        async with app.run_test() as pilot:
            statics = app.screen.query(Static)
            texts = [_get_static_text(s) for s in statics]
            assert any("hookd Setup Wizard" in t for t in texts)


# ---------------------------------------------------------------------------
# PreflightScreen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preflight_screen_shows_checklist():
    """PreflightScreen shows dependency check results and continue button."""
    fake_deps = _FakePreflightResult(found=["git", "bash"], missing=[])
    fake_ts = _FakeTailscaleStatus(logged_in=True, hostname="myhost", funnel_available=True)

    with (
        patch("hookd.steps.preflight.check_dependencies", return_value=fake_deps),
        patch("hookd.steps.preflight.check_tailscale", return_value=fake_ts),
    ):
        app = _make_app()
        async with app.run_test() as pilot:
            from hookd.tui.screens.preflight import PreflightScreen

            app.push_screen(PreflightScreen())
            await pilot.pause()

            dep_status = app.screen.query_one("#dep_status", Static)
            assert "Dependencies" in _get_static_text(dep_status)

            # Continue should be enabled when deps are met
            btn = app.screen.query_one("#continue", Button)
            assert btn.disabled is False


@pytest.mark.asyncio
async def test_preflight_screen_continue_disabled_when_missing_deps():
    """PreflightScreen disables continue when required deps are missing."""
    fake_deps = _FakePreflightResult(found=["bash"], missing=["git"])
    fake_ts = _FakeTailscaleStatus()

    with (
        patch("hookd.steps.preflight.check_dependencies", return_value=fake_deps),
        patch("hookd.steps.preflight.check_tailscale", return_value=fake_ts),
    ):
        app = _make_app()
        async with app.run_test() as pilot:
            from hookd.tui.screens.preflight import PreflightScreen

            app.push_screen(PreflightScreen())
            await pilot.pause()

            btn = app.screen.query_one("#continue", Button)
            assert btn.disabled is True


# ---------------------------------------------------------------------------
# GitHubScreen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_github_screen_has_password_input():
    """GitHubScreen has a password input for the token."""
    app = _make_app()
    async with app.run_test() as pilot:
        from hookd.tui.screens.github import GitHubScreen

        app.push_screen(GitHubScreen())
        await pilot.pause()

        token_input = app.screen.query_one("#token_input", Input)
        assert token_input is not None
        assert token_input.password is True


@pytest.mark.asyncio
async def test_github_screen_has_validate_button():
    """GitHubScreen has a validate button."""
    app = _make_app()
    async with app.run_test() as pilot:
        from hookd.tui.screens.github import GitHubScreen

        app.push_screen(GitHubScreen())
        await pilot.pause()

        btn = app.screen.query_one("#validate", Button)
        assert btn is not None

        # Continue should be disabled initially
        cont = app.screen.query_one("#continue", Button)
        assert cont.disabled is True


# ---------------------------------------------------------------------------
# EventsScreen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_events_screen_has_checkboxes():
    """EventsScreen has checkboxes for event types."""
    app = _make_app(branch="main")
    async with app.run_test() as pilot:
        from hookd.tui.screens.events import EventsScreen

        app.push_screen(EventsScreen())
        await pilot.pause()

        # Should have checkboxes for push and other event types
        push_cb = app.screen.query_one("#evt_push", Checkbox)
        assert push_cb is not None

        issues_cb = app.screen.query_one("#evt_issues", Checkbox)
        assert issues_cb is not None

        pr_cb = app.screen.query_one("#evt_pull_request", Checkbox)
        assert pr_cb is not None

        release_cb = app.screen.query_one("#evt_release", Checkbox)
        assert release_cb is not None


@pytest.mark.asyncio
async def test_events_screen_has_continue_button():
    """EventsScreen has a continue button."""
    app = _make_app(branch="main")
    async with app.run_test() as pilot:
        from hookd.tui.screens.events import EventsScreen

        app.push_screen(EventsScreen())
        await pilot.pause()

        btn = app.screen.query_one("#continue", Button)
        assert btn is not None


# ---------------------------------------------------------------------------
# SecretsScreen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_secrets_screen_generates_secret():
    """SecretsScreen generates a hex secret on init."""
    app = _make_app()
    async with app.run_test() as pilot:
        from hookd.tui.screens.secrets import SecretsScreen

        screen = SecretsScreen()
        app.push_screen(screen)
        await pilot.pause()

        # The generated secret should be a 64-char hex string
        assert len(screen._generated_secret) == 64
        assert all(c in "0123456789abcdef" for c in screen._generated_secret)


@pytest.mark.asyncio
async def test_secrets_screen_has_radio_buttons():
    """SecretsScreen has radio buttons for secret choice."""
    app = _make_app()
    async with app.run_test() as pilot:
        from hookd.tui.screens.secrets import SecretsScreen

        app.push_screen(SecretsScreen())
        await pilot.pause()

        radio_set = app.screen.query_one("#secret_choice", RadioSet)
        assert radio_set is not None

        generated_radio = app.screen.query_one("#use_generated", RadioButton)
        assert generated_radio is not None

        custom_radio = app.screen.query_one("#use_custom", RadioButton)
        assert custom_radio is not None


@pytest.mark.asyncio
async def test_secrets_screen_custom_input_hidden_by_default():
    """SecretsScreen hides custom input initially."""
    app = _make_app()
    async with app.run_test() as pilot:
        from hookd.tui.screens.secrets import SecretsScreen

        app.push_screen(SecretsScreen())
        await pilot.pause()

        custom_input = app.screen.query_one("#custom_input", Input)
        assert custom_input.display is False


# ---------------------------------------------------------------------------
# ReviewScreen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_screen_shows_summary():
    """ReviewScreen shows configuration summary."""
    app = _make_app(
        full_name="octocat/hello-world",
        github_user="octocat",
        webhook_secret="abcdef1234567890abcdef1234567890",
        events_config=[
            {"name": "push", "branches": {"main": "handlers/push-main.sh"}},
        ],
    )
    async with app.run_test() as pilot:
        from hookd.tui.screens.review import ReviewScreen

        app.push_screen(ReviewScreen())
        await pilot.pause()

        # Check that the review screen title is present
        title_static = app.screen.query(Static)
        all_text = " ".join(_get_static_text(s) for s in title_static)
        assert "octocat/hello-world" in all_text
        assert "Review Configuration" in all_text


@pytest.mark.asyncio
async def test_review_screen_has_deploy_button():
    """ReviewScreen has deploy and back buttons."""
    app = _make_app(
        full_name="test/repo",
        github_user="test",
        webhook_secret="a" * 32,
        events_config=[],
    )
    async with app.run_test() as pilot:
        from hookd.tui.screens.review import ReviewScreen

        app.push_screen(ReviewScreen())
        await pilot.pause()

        deploy_btn = app.screen.query_one("#deploy", Button)
        assert deploy_btn is not None

        back_btn = app.screen.query_one("#back", Button)
        assert back_btn is not None


# ---------------------------------------------------------------------------
# DoneScreen
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_done_screen_has_finish_button():
    """DoneScreen has a finish button."""
    app = _make_app(full_name="octocat/hello-world")
    async with app.run_test() as pilot:
        from hookd.tui.screens.done import DoneScreen

        app.push_screen(DoneScreen())
        await pilot.pause()

        btn = app.screen.query_one("#finish", Button)
        assert btn is not None


@pytest.mark.asyncio
async def test_done_screen_shows_webhook_url():
    """DoneScreen displays the funnel URL."""
    app = _make_app(
        full_name="octocat/hello-world",
        funnel_url="https://myhost:9876/webhook",
    )
    async with app.run_test() as pilot:
        from hookd.tui.screens.done import DoneScreen

        app.push_screen(DoneScreen())
        await pilot.pause()

        statics = app.screen.query(Static)
        all_text = " ".join(_get_static_text(s) for s in statics)
        assert "https://myhost:9876/webhook" in all_text


@pytest.mark.asyncio
async def test_done_screen_shows_commands():
    """DoneScreen displays helpful commands."""
    app = _make_app(full_name="test/repo")
    async with app.run_test() as pilot:
        from hookd.tui.screens.done import DoneScreen

        app.push_screen(DoneScreen())
        await pilot.pause()

        statics = app.screen.query(Static)
        all_text = " ".join(_get_static_text(s) for s in statics)
        assert "hookd status" in all_text
        assert "hookd test" in all_text
