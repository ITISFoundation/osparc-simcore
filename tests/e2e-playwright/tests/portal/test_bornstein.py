# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Port of the legacy tests/e2e/portal/Bornstein.js Puppeteer script."""

import contextlib
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import check_node_outputs, get_node_id_from_service_key, wait_for_service_running
from pytest_simcore.helpers.playwright_portal import restore_iframe

# NOTE: bornstein-viewer is a legacy dynamic service (port of the legacy Bornstein.js, which calls
# `waitForServices(..., waitForConnected=true)`), so the websocket node-progress path never fires.
_IS_SERVICE_LEGACY = True

# Dash inserts this element while a callback (i.e. the computation) is running
_DASH_LOADING_CALLBACK_SELECTOR = "._dash-loading-callback"
_DASH_LOADING_CALLBACK_APPEAR_TIMEOUT = 30 * 1000

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

    loading_callback = iframe_locator.locator(_DASH_LOADING_CALLBACK_SELECTOR)
    # best-effort: the computation may already be done by the time we get here
    with log_context(
        logging.INFO,
        "Waiting for Bornstein computation to finish "
        f"(timeout={timedelta(milliseconds=2 * _DASH_LOADING_CALLBACK_APPEAR_TIMEOUT)})",
    ):
        with contextlib.suppress(PlaywrightTimeoutError, TimeoutError):
            loading_callback.wait_for(state="attached", timeout=_DASH_LOADING_CALLBACK_APPEAR_TIMEOUT)
        loading_callback.wait_for(state="detached", timeout=_DASH_LOADING_CALLBACK_APPEAR_TIMEOUT)

    check_node_outputs(
        page,
        study_id=project_data["uuid"],
        node_position=0,
        expected_file_names=_EXPECTED_OUTPUT_FILES,
    )
