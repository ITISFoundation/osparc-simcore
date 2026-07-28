# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/publications/Voila.js Puppeteer script."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page
from pytest_simcore.helpers.playwright import wait_for_service_running
from pytest_simcore.helpers.playwright_portal import wait_for_voila_iframe, wait_for_voila_rendered

# NOTE: the voila-viewer node is a legacy dynamic service (port of the legacy Voila.js, which calls
# `waitForServices(..., waitForConnected=true)`), so the websocket node-progress path never fires.
_IS_SERVICE_LEGACY = True


def test_voila(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    service_start_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    workbench = opened_study.project_data["workbench"]
    # single-node study: port of the legacy `extractWorkbenchData(data).nodeIds[0]`
    voila_node_id = next(iter(workbench))

    wait_for_service_running(
        page=page,
        node_id=voila_node_id,
        websocket=opened_study.websocket,
        timeout=service_start_timeout,
        press_start_button=False,
        product_url=opened_study.product_url,
        is_service_legacy=_IS_SERVICE_LEGACY,
    )

    # wait for iframe to be ready, it might take a while in Voila
    iframe_locator = wait_for_voila_iframe(page, voila_node_id)
    wait_for_voila_rendered(iframe_locator)
