# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import logging
from typing import Final

import pytest
from playwright.sync_api import Page, expect
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import SECOND, RobustWebSocket

_TOUR_STEP_TIMEOUT: Final[int] = 30 * SECOND
_TOUR_STEP_WAIT_BETWEEN: Final[int] = 500  # ms


# Available tours in osparc_tours.json
OSPARC_TOURS: Final[list[dict]] = [
    {"id": "projects", "name": "Projects", "steps": 6},
    {"id": "dashboard", "name": "Dashboard", "steps": 5},
    {"id": "navbar", "name": "Navigation Bar", "steps": 3},
]


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


def _run_tour(page: Page, tour_id: str, expected_steps: int) -> None:
    """Run through all steps of a specific tour."""
    with log_context(logging.INFO, f"Starting tour: {tour_id}"):
        # Click on the tour list item to start it
        tour_item = page.get_by_test_id(f"tourListItem-{tour_id}")
        expect(tour_item).to_be_visible(timeout=_TOUR_STEP_TIMEOUT)
        tour_item.click()

        # The manager window closes and tour steps begin
        page.wait_for_timeout(_TOUR_STEP_WAIT_BETWEEN)

    # Go through each step
    for step_num in range(1, expected_steps + 1):
        with log_context(logging.INFO, f"Tour '{tour_id}' - Step {step_num}/{expected_steps}"):
            # Wait for the Next button to appear
            next_btn = page.get_by_test_id("tourStepNextBtn")
            expect(next_btn).to_be_visible(timeout=_TOUR_STEP_TIMEOUT)

            # On the last step, the button says "End" instead of "Next"
            if step_num == expected_steps:
                expect(next_btn).to_have_text("End", timeout=_TOUR_STEP_TIMEOUT)

            # Click to proceed to next step (or end the tour)
            next_btn.click()
            page.wait_for_timeout(_TOUR_STEP_WAIT_BETWEEN)

    with log_context(logging.INFO, f"Tour '{tour_id}' completed"):
        # After clicking End, the "To Tours" button appears briefly
        # but the tour manager may show or close depending on implementation
        # Just wait a moment for the UI to settle
        page.wait_for_timeout(_TOUR_STEP_WAIT_BETWEEN)


@pytest.mark.parametrize(
    "tour_info",
    OSPARC_TOURS,
    ids=[t["id"] for t in OSPARC_TOURS],
)
def test_guided_tour(
    page: Page,
    log_in_and_out: RobustWebSocket,
    tour_info: dict,
    tour_id: str | None,
):
    """
    Test that goes through each guided tour step by step.

    This test will:
    1. Open the Support Center
    2. Click on Guided Tours
    3. Select the specified tour
    4. Click through all steps until completion
    """
    # Skip if a specific tour was requested and this isn't it
    if tour_id is not None and tour_info["id"] != tour_id:
        pytest.skip(f"Skipping tour '{tour_info['id']}' - only running '{tour_id}'")

    with log_context(
        logging.INFO,
        f"Running guided tour: {tour_info['name']} ({tour_info['steps']} steps)",
    ):
        _open_guided_tours_manager(page)
        _run_tour(page, tour_info["id"], tour_info["steps"])

    # Verify we're back on the dashboard (tours should end there)
    expect(page.get_by_test_id("studiesTabBtn")).to_be_visible(timeout=_TOUR_STEP_TIMEOUT)
