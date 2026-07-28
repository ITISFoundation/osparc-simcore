"""Helpers shared by the tests/e2e-playwright/tests/portal test suite.

These tests port the legacy Puppeteer scripts in tests/e2e/portal, tests/e2e/portal-files and
tests/e2e/publications, which open a public/portal study without logging in
(see `open_study_link` fixture in tests/e2e-playwright/tests/conftest.py) and interact with the
service(s) it contains.

NOTE: only helpers reused by more than one test live here. Logic specific to a single test
lives in that test's module instead.
"""

from playwright.sync_api import Page


def restore_iframe(page: Page) -> None:
    """Restores a maximized/fullscreen iframe. Port of the legacy `auto.restoreIFrame()`."""
    page.get_by_test_id("restoreBtn").click()
