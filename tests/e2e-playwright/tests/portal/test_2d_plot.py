# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/2D_Plot.js Puppeteer script."""

import logging
from collections.abc import Callable
from typing import Any

from playwright.sync_api import FrameLocator, Locator, Page
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import get_node_id_from_service_key, wait_for_service_running
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_fixed

# NOTE: raw-graphs is a legacy dynamic service (port of the legacy 2D_Plot.js, which calls
# `waitForServices(..., waitForConnected=true)`), so the websocket node-progress path never fires.
_IS_SERVICE_LEGACY = True


@retry(
    retry=retry_if_exception_type(AssertionError),
    stop=stop_after_delay(60),
    wait=wait_fixed(3),
    reraise=True,
)
def _click_osparc_inputs_and_get_file_item(page: Page, iframe_locator: FrameLocator) -> Locator:
    """Clicks "oSPARC inputs" and returns the file item locator once it is visible.

    NOTE: the raw-graphs app can take a variable amount of time to fetch/render the list of
    available oSPARC inputs after the button is clicked (and occasionally the first click doesn't
    seem to trigger it at all), so this retries the click until the file item shows up.
    """
    iframe_locator.get_by_text("oSPARC inputs").click()
    page.wait_for_timeout(2000)
    file_item = iframe_locator.get_by_text("RNAdat.csv")
    assert file_item.is_visible(), "file item not visible yet"
    return file_item


def test_2d_plot(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    service_start_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    workbench = opened_study.project_data["workbench"]
    node_id = get_node_id_from_service_key(workbench, "raw-graphs")

    iframe_locator = wait_for_service_running(
        page=page,
        node_id=node_id,
        websocket=opened_study.websocket,
        timeout=service_start_timeout,
        press_start_button=False,
        product_url=opened_study.product_url,
        is_service_legacy=_IS_SERVICE_LEGACY,
    )

    iframe_locator.get_by_text("oSPARC inputs").wait_for(state="visible")

    with log_context(logging.INFO, "Clicking on oSPARC inputs"):
        file_item = _click_osparc_inputs_and_get_file_item(page, iframe_locator)

    with log_context(logging.INFO, "Clicking on the input coming from the File Picker"):
        file_item.click()
