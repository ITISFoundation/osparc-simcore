"""Helpers shared by the tests/e2e-playwright/tests/portal test suite.
NOTE: only helpers reused by more than one test live here. Logic specific to a single test
lives in that test's module instead.
"""

from playwright.sync_api import Page


def restore_iframe(page: Page) -> None:
    """Restores a maximized/fullscreen iframe. Port of the legacy `auto.restoreIFrame()`."""
    page.get_by_test_id("restoreBtn").click()
