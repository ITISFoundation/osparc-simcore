# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import contextlib
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, Final

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    check_node_files_panel,
    get_node_id_from_service_key,
    wait_for_service_running,
)
from pytest_simcore.helpers.playwright_portal import restore_iframe

# NOTE: bornstein-viewer is a legacy dynamic service (port of the legacy Bornstein.js, which calls
# `waitForServices(..., waitForConnected=true)`), so the websocket node-progress path never fires.
_IS_SERVICE_LEGACY = True

# Dash inserts this element while a callback (i.e. the computation) is running
_DASH_LOADING_CALLBACK_SELECTOR = "._dash-loading-callback"

# The spinner ships inside Dash's index HTML, but waiting for it also covers the iframe's own render,
# so this stays generous; it is not part of the computation budget. The failing CI runs' own timings
# put it at 0.5-1.4 s, i.e. the old single 30 s budget was never protecting the iframe load.
_DASH_LOADING_CALLBACK_APPEAR_TIMEOUT: Final[int] = 30 * SECOND

# The Bornstein solver runs synchronously inside the service, in the initial Dash callback (a POST to
# `_dash-update-component` that only answers when the computation is done). Measured on a busy master
# deployment: ~20 s typically, ~31 s at worst, so the budget has to sit well above that or ordinary
# latency jitter turns the run red. Kept equal to the 2-minute service-start budget the CI job grants.
_DASH_COMPUTATION_TIMEOUT: Final[int] = 2 * MINUTE

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
    with log_context(
        logging.INFO,
        f"Waiting for Bornstein computation to finish (timeout={timedelta(milliseconds=_DASH_COMPUTATION_TIMEOUT)})",
    ):
        # best-effort: the computation may already be done by the time we get here
        with contextlib.suppress(PlaywrightTimeoutError, TimeoutError):
            loading_callback.wait_for(state="attached", timeout=_DASH_LOADING_CALLBACK_APPEAR_TIMEOUT)
        loading_callback.wait_for(state="detached", timeout=_DASH_COMPUTATION_TIMEOUT)

    check_node_files_panel(
        page,
        study_id=project_data["uuid"],
        workbench=project_data["workbench"],
        node_position=0,
        expected_file_names=_EXPECTED_OUTPUT_FILES,
    )
