# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
import logging
from pathlib import Path
from typing import Final

import pytest
from playwright.sync_api import Page, expect
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import SECOND, RobustWebSocket

_TOUR_STEP_TIMEOUT: Final[int] = 30 * SECOND
_TOUR_STEP_WAIT_BETWEEN: Final[int] = 500  # ms
_MAX_TOUR_STEPS: Final[int] = 20  # Safety limit to avoid infinite loops

# Path to osparc_tours.json relative to repository root
_OSPARC_TOURS_JSON: Final[Path] = (
    Path(__file__).parents[4]
    / "services"
    / "static-webserver"
    / "client"
    / "source"
    / "resource"
    / "osparc"
    / "tours"
    / "osparc_tours.json"
)


def _load_osparc_tours() -> list[dict]:
    """Load tours from osparc_tours.json."""
    with _OSPARC_TOURS_JSON.open() as f:
        tours_data = json.load(f)
    return [{"id": tour["id"], "name": tour["name"]} for tour in tours_data.values()]


OSPARC_TOURS: Final[list[dict]] = _load_osparc_tours()


def _open_guided_tours_manager(page: Page) -> None:
    """Open the Guided Tours Manager window via Support Center."""
    with log_context(logging.INFO, "Opening Support Center..."):
        page.get_by_test_id("supportButton").click()
        # Wait for Support Center to open
        expect(page.get_by_test_id("supportCenterWindow")).to_be_visible(timeout=_TOUR_STEP_TIMEOUT)

    with log_context(logging.INFO, "Opening Guided Tours Manager..."):
        page.get_by_test_id("guidedToursBtn").click()
        # Wait for Guided Tours Manager to open
        expect(page.get_by_test_id("guidedToursManager")).to_be_visible(timeout=_TOUR_STEP_TIMEOUT)


def _run_tour(page: Page, tour_id: str) -> None:
    """
    Run through all steps of a specific tour.

    The tour manager may skip steps if the target elements aren't visible
    (e.g., no projects listed). This function clicks Next until it reaches
    the End button, regardless of how many steps are actually shown.
    """
    with log_context(logging.INFO, f"Starting tour: {tour_id}"):
        # Click on the tour list item to start it
        tour_item = page.get_by_test_id(f"tourListItem-{tour_id}")
        expect(tour_item).to_be_visible(timeout=_TOUR_STEP_TIMEOUT)
        tour_item.click()

        # The manager window closes and tour steps begin
        page.wait_for_timeout(_TOUR_STEP_WAIT_BETWEEN)

    # Go through each step until we reach "End"
    step_num = 0
    while step_num < _MAX_TOUR_STEPS:
        step_num += 1
        with log_context(logging.INFO, f"Tour '{tour_id}' - Step {step_num}"):
            # Wait for the Next button to appear
            next_btn = page.get_by_test_id("tourStepNextBtn")
            expect(next_btn).to_be_visible(timeout=_TOUR_STEP_TIMEOUT)

            # Check if this is the last step (button says "End")
            button_text = next_btn.inner_text()
            is_last_step = button_text == "End"

            # Click to proceed to next step (or end the tour)
            next_btn.click()
            page.wait_for_timeout(_TOUR_STEP_WAIT_BETWEEN)

            if is_last_step:
                break

    with log_context(logging.INFO, f"Tour '{tour_id}' completed after {step_num} step(s)"):
        # Wait a moment for the UI to settle
        page.wait_for_timeout(_TOUR_STEP_WAIT_BETWEEN)


def test_guided_tours(
    page: Page,
    log_in_and_out: RobustWebSocket,
    tour_id: str | None,
):
    """
    Test that goes through all guided tours step by step using a single user session.

    This test will:
    1. Open the Support Center
    2. Click on Guided Tours
    3. Select each tour and click through all steps until completion

    Steps may be skipped by the tour manager if target elements aren't visible.
    The test passes as long as each tour reaches the "End" button.
    """
    tours_to_run = OSPARC_TOURS
    if tour_id is not None:
        tours_to_run = [t for t in OSPARC_TOURS if t["id"] == tour_id]
        if not tours_to_run:
            pytest.skip(f"Tour '{tour_id}' not found")

    for tour_info in tours_to_run:
        # Make sure we are in the Projects tab, My workspace before each tour
        page.get_by_test_id("studiesTabBtn").click()
        page.get_by_test_id("workspacesAndFoldersTreeItem_null_null").click()

        with log_context(
            logging.INFO,
            f"Running guided tour: {tour_info['name']}",
        ):
            _open_guided_tours_manager(page)
            _run_tour(page, tour_info["id"])
