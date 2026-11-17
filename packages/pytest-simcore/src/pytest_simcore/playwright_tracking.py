"""Fixtures overriding pytest-playwright's `context`/`page` to record every page's websockets.

Consumers opt in in their conftest:

    from pytest_simcore.playwright_tracking import context, page

    __all__ = ["context", "page"]

`context` attaches a `page` listener so every page created in the context -- including
popups and `context.new_page()` -- starts tracking before its first navigation, which is
when `RobustWebSocket` needs the history to adopt a socket.io reconnection (see
`start_websocket_tracking`). `page` covers pages created before the listener could run;
both fixtures are idempotent.
"""

import pytest
from playwright.sync_api import BrowserContext, Page

from .helpers.playwright import start_websocket_tracking


@pytest.fixture
def context(context: BrowserContext) -> BrowserContext:
    context.on("page", start_websocket_tracking)
    return context


@pytest.fixture
def page(page: Page) -> Page:
    start_websocket_tracking(page)
    return page
