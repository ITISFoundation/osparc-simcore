"""Helpers shared by the tests/e2e-playwright/tests/portal test suite.

These tests port the legacy Puppeteer scripts in tests/e2e/portal, tests/e2e/portal-files and
tests/e2e/publications, which open a public/portal study without logging in
(see `open_study_link` fixture in tests/e2e-playwright/tests/conftest.py) and interact with the
service(s) it contains.

NOTE: only helpers reused by more than one test live here. Logic specific to a single test
lives in that test's module instead.
"""

import logging
from typing import Final

from playwright.sync_api import FrameLocator, Page

from .logging_tools import log_context
from .playwright import SECOND

_VOILA_IFRAME_MAX_WAIT_TIME: Final[int] = 4 * 60 * SECOND
_VOILA_RENDERED_MAX_WAIT_TIME: Final[int] = 2 * 60 * SECOND


def restore_iframe(page: Page) -> None:
    """Restores a maximized/fullscreen iframe. Port of the legacy `auto.restoreIFrame()`."""
    page.get_by_test_id("restoreBtn").click()


def wait_for_voila_iframe(page: Page, node_id: str, *, timeout_ms: int = _VOILA_IFRAME_MAX_WAIT_TIME) -> FrameLocator:
    """Waits for the Voila iframe to appear (it can take a while to render).

    Port of `TutorialBase.waitForVoilaIframe()`.
    """
    iframe_locator = page.frame_locator(f'[osparc-test-id="iframe_{node_id}"]')
    with log_context(logging.INFO, f"Waiting for Voila iframe of node {node_id=}"):
        page.locator(f'[osparc-test-id="iframe_{node_id}"]').wait_for(state="attached", timeout=timeout_ms)
    return iframe_locator


def wait_for_voila_rendered(iframe_locator: FrameLocator, *, timeout_ms: int = _VOILA_RENDERED_MAX_WAIT_TIME) -> None:
    """Waits until the Voila notebook has finished rendering.

    Port of `TutorialBase.waitForVoilaRendered()`.
    """
    with log_context(logging.INFO, "Waiting for Voila to render"):
        iframe_locator.locator("#rendered_cells").wait_for(state="visible", timeout=timeout_ms)
