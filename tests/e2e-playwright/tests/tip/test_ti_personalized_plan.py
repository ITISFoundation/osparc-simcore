# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from playwright.sync_api import Page, WebSocket
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    RobustWebSocket,
)
from tenacity import retry, stop_after_delay, wait_fixed

_OUTER_EXPECT_TIMEOUT_RATIO: Final[float] = 1.1
_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE

_ELECTRODE_SELECTOR_MAX_STARTUP_TIME: Final[int] = 2 * MINUTE
_ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME: Final[int] = 3 * MINUTE
_ELECTRODE_SELECTOR_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME + _ELECTRODE_SELECTOR_MAX_STARTUP_TIME
)
_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME: Final[int] = 5 * SECOND


_JLAB_MAX_STARTUP_MAX_TIME: Final[int] = 3 * MINUTE
_JLAB_DOCKER_PULLING_MAX_TIME: Final[int] = 12 * MINUTE
_JLAB_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _JLAB_DOCKER_PULLING_MAX_TIME + _JLAB_MAX_STARTUP_MAX_TIME
)
_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME: Final[int] = 2 * MINUTE
_JLAB_RUN_OPTIMIZATION_MAX_TIME: Final[int] = 4 * MINUTE
_JLAB_REPORTING_MAX_TIME: Final[int] = 60 * SECOND


_POST_PRO_MAX_STARTUP_TIME: Final[int] = 2 * MINUTE
_POST_PRO_DOCKER_PULLING_MAX_TIME: Final[int] = 12 * MINUTE
_POST_PRO_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _POST_PRO_DOCKER_PULLING_MAX_TIME + _POST_PRO_MAX_STARTUP_TIME
)


@dataclass
class _JLabWaitForWebSocket:
    def __call__(self, new_websocket: WebSocket) -> bool:
        with log_context(logging.DEBUG, msg=f"received {new_websocket=}"):
            return bool(re.search("/api/kernels/[^/]+/channels", new_websocket.url))


@retry(
    stop=stop_after_delay(_JLAB_RUN_OPTIMIZATION_MAX_TIME / 1000),  # seconds
    wait=wait_fixed(2),
    reraise=True,
)
def _wait_for_optimization_complete(run_button):
    bg_color = run_button.evaluate("el => getComputedStyle(el).backgroundColor")
    if bg_color != "rgb(0, 128, 0)":
        msg = f"Optimization not finished yet: {bg_color=}, {run_button=}"
        raise ValueError(msg)


def test_personalized_classic_ti_plan(
    page: Page,
    log_in_and_out: RobustWebSocket,
    is_autoscaled: bool,
    is_product_lite: bool,
    create_tip_plan_from_dashboard: Callable[[str], dict[str, Any]],
    product_url: AnyUrl,
    is_service_legacy: bool,
    playwright_test_results_dir: Path,
):
    with log_context(logging.INFO, "Checking there is no 'Access TIP' teaser"):
        # click to open and expand
        page.get_by_test_id("userMenuBtn").click()
        assert page.get_by_test_id("userMenuAccessTIPBtn").count() == 0, "full version should NOT have a teaser"
        # click to close
        page.get_by_test_id("userMenuBtn").click()

    # press + button
    project_data = create_tip_plan_from_dashboard("newPTIPlanButton")
    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(project_data["workbench"], dict), "Expected workbench to be a dict!"
    node_ids: list[str] = list(project_data["workbench"])

    # wallet selection

    # 1. File Picker (file-picker)
    # 2. Personalizer (ti-pers)
    # 3. Model Inspector (sim4life-modeling)
    # 4. Simulator (ti-simu)
    # 5. Classic TI (ti-postpro)
    # 6. Exposure Analysis (sim4life-postpro)

    # count the number of elements with test id matching the pattern
    expected_number_of_steps = 6
    step_buttons = page.locator("[osparc-test-id^='AppMode_StepBtn_']")
    assert step_buttons.count() == expected_number_of_steps, (
        f"Expected {expected_number_of_steps} step buttons, found {step_buttons.count()}"
    )
    assert len(node_ids) >= expected_number_of_steps, (
        f"Expected at least {expected_number_of_steps} nodes in the workbench"
    )
