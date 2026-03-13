import pytest

from hookd.tui.app import HookdApp


@pytest.mark.asyncio
async def test_app_starts():
    app = HookdApp()
    async with app.run_test() as pilot:
        assert app.title == "hookd"


@pytest.mark.asyncio
async def test_app_with_context():
    ctx = {"owner": "test", "repo": "repo"}
    app = HookdApp(context=ctx)
    async with app.run_test() as pilot:
        assert app.context["owner"] == "test"
