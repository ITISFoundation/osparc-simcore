# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/BIOS_VNS_Calibrator.js Puppeteer script."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page, expect
from pytest_simcore.helpers.playwright import get_node_id_from_service_key, wait_for_service_running
from pytest_simcore.helpers.playwright_portal import restore_iframe

# NOTE: port of the legacy BIOS_VNS_Calibrator.js, which calls
# `waitForServices(..., waitForConnected=false)`
_IS_SERVICE_LEGACY = False


def test_bios_vns_calibrator(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    service_start_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    workbench = opened_study.project_data["workbench"]
    node_id = get_node_id_from_service_key(workbench, "bios-health-vns-calibrator")

    iframe_locator = wait_for_service_running(
        page=page,
        node_id=node_id,
        websocket=opened_study.websocket,
        timeout=service_start_timeout,
        press_start_button=False,
        product_url=opened_study.product_url,
        is_service_legacy=_IS_SERVICE_LEGACY,
    )

    # This study opens in fullscreen mode
    restore_iframe(page)

    expect(iframe_locator.locator("body")).to_be_visible()
