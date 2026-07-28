# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/Bornstein.js Puppeteer script."""

from collections.abc import Callable
from typing import Any

from playwright.sync_api import Page
from pytest_simcore.helpers.playwright import get_node_id_from_service_key, wait_for_service_running
from pytest_simcore.helpers.playwright_portal import check_node_outputs, restore_iframe

# NOTE: bornstein-viewer is a legacy dynamic service (port of the legacy Bornstein.js, which calls
# `waitForServices(..., waitForConnected=true)`), so the websocket node-progress path never fires.
_IS_SERVICE_LEGACY = True

_EXPECTED_OUTPUT_FILES: list[str] = [
    "output.csv",
    "traces.pkl",
]


def test_bornstein(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    service_start_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    project_data = opened_study.project_data
    node_id = get_node_id_from_service_key(project_data["workbench"], "bornstein-viewer")

    wait_for_service_running(
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

    check_node_outputs(
        page,
        websocket=opened_study.websocket,
        study_id=project_data["uuid"],
        node_position=0,
        expected_file_names=_EXPECTED_OUTPUT_FILES,
    )
