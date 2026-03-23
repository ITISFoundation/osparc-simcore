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

import pytest
from playwright.sync_api import Page, WebSocket, expect
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    RobustWebSocket,
    app_mode_trigger_next_app,
    expected_service_running,
)
from tenacity import retry, stop_after_attempt, wait_fixed

_OUTER_EXPECT_TIMEOUT_RATIO: Final[float] = 1.1
_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE


_JLAB_MAX_STARTUP_MAX_TIME: Final[int] = 3 * MINUTE
_JLAB_DOCKER_PULLING_MAX_TIME: Final[int] = 12 * MINUTE
_JLAB_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _JLAB_DOCKER_PULLING_MAX_TIME + _JLAB_MAX_STARTUP_MAX_TIME
)
_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME: Final[int] = 2 * MINUTE
_JLAB_RUN_OPTIMIZATION_MAX_TIME: Final[int] = 4 * MINUTE
_JLAB_REPORTING_MAX_TIME: Final[int] = 60 * SECOND

_PERSONALIZATION_MAX_TIME: Final[int] = 10 * MINUTE


_MODELING_MAX_STARTUP_TIME: Final[int] = 2 * MINUTE
_MODELING_DOCKER_PULLING_MAX_TIME: Final[int] = 12 * MINUTE
_MODELING_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _MODELING_DOCKER_PULLING_MAX_TIME + _MODELING_MAX_STARTUP_TIME
)

_SIMULATOR_MAX_STARTUP_TIME: Final[int] = 3 * MINUTE
_SIMULATOR_DOCKER_PULLING_MAX_TIME: Final[int] = 12 * MINUTE
_SIMULATOR_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _SIMULATOR_DOCKER_PULLING_MAX_TIME + _SIMULATOR_MAX_STARTUP_TIME
)
_SIMULATOR_SETUP_APPEARANCE_TIME: Final[int] = 2 * MINUTE
_SIMULATION_MAX_TIME: Final[int] = 42 * MINUTE

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
    stop=stop_after_attempt(5),
    wait=wait_fixed(60),
    reraise=True,
)
def _wait_for_personalization_complete(start_button, outputs_button):
    icon_class = start_button.locator("i").first.evaluate("el => el.className")
    outputs_text = outputs_button.inner_text()
    if "fa-check" not in icon_class or "Outputs (6)" not in outputs_text:
        msg = f"Personalization still running: {icon_class=}, {outputs_text=}"
        raise ValueError(msg)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(60),
    reraise=True,
)
def _wait_for_simulation_complete(setup_button, export_button):
    icon_class = setup_button.locator("i").first.evaluate("el => el.className")
    is_enabled = export_button.evaluate("el => !el.disabled")
    if "fa-spinner" in icon_class or not is_enabled:
        msg = f"Simulation still running: {icon_class=}, export enabled={is_enabled}"
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
    if is_product_lite:
        pytest.skip("Personalized classic TI plan test is only applicable to full product.")

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

    # count the number of elements with test id matching the pattern
    # 0. File Picker with the test_data already uploaded (file-picker) - it is not exposed
    # 1. File Picker (file-picker)
    # 2. Personalizer (ti-pers (voila))
    # 3. Model Inspector (sim4life-modeling)
    # 4. Simulator (ti-simu)
    # 5. Classic TI (ti-postpro)
    # 6. Exposure Analysis (sim4life-postpro)
    expected_number_of_steps = 6
    step_buttons = page.locator("[osparc-test-id^='AppMode_StepBtn_']")
    assert step_buttons.count() == expected_number_of_steps, (
        f"Expected {expected_number_of_steps} step buttons, found {step_buttons.count()}"
    )
    assert len(node_ids) >= expected_number_of_steps, (
        f"Expected at least {expected_number_of_steps} nodes in the workbench"
    )

    with log_context(logging.INFO, "File Picker step (1/%s)", expected_number_of_steps):
        # in the testing project the file is already uploaded, so just check the file is already there
        file_picker_step = page.get_by_test_id("AppMode_StepBtn_1")
        # wait 2 seconds to show the File in the tracer
        page.wait_for_timeout(2 * SECOND)
        expect(file_picker_step).not_to_contain_text("Select a file", timeout=10 * SECOND)

    with log_context(logging.INFO, "Personalizer step (2/%s)", expected_number_of_steps):
        with page.expect_websocket(
            _JLabWaitForWebSocket(),
            timeout=_OUTER_EXPECT_TIMEOUT_RATIO
            * (_JLAB_AUTOSCALED_MAX_STARTUP_TIME if is_autoscaled else _JLAB_MAX_STARTUP_MAX_TIME),
        ) as ws_info:
            with expected_service_running(
                page=page,
                node_id=node_ids[2],
                websocket=log_in_and_out,
                timeout=(_JLAB_AUTOSCALED_MAX_STARTUP_TIME if is_autoscaled else _JLAB_MAX_STARTUP_MAX_TIME),
                press_start_button=False,
                product_url=product_url,
                is_service_legacy=is_service_legacy,
            ) as service_running:
                app_mode_trigger_next_app(page)
            personalizer_iframe = service_running.iframe_locator
            assert personalizer_iframe

        assert not ws_info.value.is_closed()

        with log_context(logging.INFO, "Start personalization"):
            start_button = personalizer_iframe.get_by_role("button", name="Start")
            start_button.click(timeout=_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME)
            page.wait_for_timeout(_PERSONALIZATION_MAX_TIME)
            outputs_button = page.get_by_test_id("outputsBtn")
            _wait_for_personalization_complete(start_button, outputs_button)

    with log_context(logging.INFO, "Model Inspector step (3/%s)", expected_number_of_steps):
        with expected_service_running(
            page=page,
            node_id=node_ids[3],
            websocket=log_in_and_out,
            timeout=(_MODELING_AUTOSCALED_MAX_STARTUP_TIME if is_autoscaled else _MODELING_MAX_STARTUP_TIME),
            press_start_button=False,
            product_url=product_url,
            is_service_legacy=is_service_legacy,
        ) as service_running:
            app_mode_trigger_next_app(page)
        modeling_iframe = service_running.iframe_locator
        assert modeling_iframe

    with log_context(logging.INFO, "Simulator step (4/%s)", expected_number_of_steps):
        with page.expect_websocket(
            _JLabWaitForWebSocket(),
            timeout=_OUTER_EXPECT_TIMEOUT_RATIO
            * (_SIMULATOR_AUTOSCALED_MAX_STARTUP_TIME if is_autoscaled else _SIMULATOR_MAX_STARTUP_TIME),
        ) as ws_info:
            with expected_service_running(
                page=page,
                node_id=node_ids[4],
                websocket=log_in_and_out,
                timeout=(_SIMULATOR_AUTOSCALED_MAX_STARTUP_TIME if is_autoscaled else _SIMULATOR_MAX_STARTUP_TIME),
                press_start_button=False,
                product_url=product_url,
                is_service_legacy=is_service_legacy,
            ) as service_running:
                app_mode_trigger_next_app(page)
            simulator_iframe = service_running.iframe_locator
            assert simulator_iframe

        assert not ws_info.value.is_closed()

        with log_context(logging.INFO, "Setup simulation"):
            setup_button = simulator_iframe.get_by_role("button", name="Setup")
            setup_button.click(timeout=_SIMULATOR_SETUP_APPEARANCE_TIME)
