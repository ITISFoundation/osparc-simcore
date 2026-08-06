# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import re
from collections.abc import Callable
from typing import Any

from playwright.sync_api import FrameLocator, Page
from pytest_simcore.helpers.playwright import get_node_id_from_service_key, wait_for_service_running

# NOTE: port of the legacy SarValidation.js, which calls `waitForServices(..., waitForConnected=false)`
_IS_SERVICE_LEGACY = False


def _run_sar_validation_interactions(page: Page, iframe_locator: FrameLocator) -> None:
    """Generates and exports a training set. Port of `TutorialBase.testSARValidation()`."""
    with (
        page.expect_response(re.compile(r"training-set-generation/generate")),
        page.expect_response(re.compile(r"training-set-generation/data")),
    ):
        iframe_locator.get_by_test_id("createTrainingSetBtn").click()

    with page.expect_response(re.compile(r"training-set-generation/xport")):
        iframe_locator.get_by_test_id("exportTrainingSetBtn").click()


def test_sar_validation(
    page: Page,
    open_study_link: Callable[..., Any],
    anonymous_study_url: str,
    service_start_timeout: int,
) -> None:
    opened_study = open_study_link(anonymous_study_url)
    workbench = opened_study.project_data["workbench"]
    node_id = get_node_id_from_service_key(workbench, "iec62209-web")

    iframe_locator = wait_for_service_running(
        page=page,
        node_id=node_id,
        websocket=opened_study.websocket,
        timeout=service_start_timeout,
        press_start_button=False,
        product_url=opened_study.product_url,
        is_service_legacy=_IS_SERVICE_LEGACY,
    )

    _run_sar_validation_interactions(page, iframe_locator)
