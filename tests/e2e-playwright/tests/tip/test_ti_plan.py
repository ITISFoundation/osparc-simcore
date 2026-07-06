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
from types import SimpleNamespace
from typing import Any, Final

from _tip_steps import (
    POST_PRO_AUTOSCALED_MAX_STARTUP_TIME,
    POST_PRO_LOAD_ANALYSIS_MAX_TIME,
    POST_PRO_LOAD_APPEARANCE_TIME,
    POST_PRO_LOAD_RESULT_MAX_TIME,
    POST_PRO_MAX_STARTUP_TIME,
    POST_PRO_REPORTING_MAX_TIME,
    POST_PRO_RUN_OPTIMIZATION_MAX_TIME,
    POST_PRO_TARGET_TISSUE_APPEARANCE_TIME,
    get_node_id_from_service_key,
    run_optimization_and_load_analysis,
    set_fast_optimization_settings,
    wait_and_select_target_tissue,
    wait_for_export_complete,
)
from playwright.sync_api import Page, WebSocket, expect
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    RobustWebSocket,
    SocketIOWaitNodeForOutputs,
    app_mode_trigger_next_app,
    decode_socketio_42_message,
    expected_service_running,
    wait_for_service_running,
)

_OUTER_EXPECT_TIMEOUT_RATIO: Final[float] = 1.1
_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE

_ELECTRODE_SELECTOR_MAX_STARTUP_TIME: Final[int] = 2 * MINUTE
_ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME: Final[int] = 3 * MINUTE
_ELECTRODE_SELECTOR_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME + _ELECTRODE_SELECTOR_MAX_STARTUP_TIME
)
_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME: Final[int] = 5 * SECOND


@dataclass
class _JLabWaitForWebSocket:
    def __call__(self, new_websocket: WebSocket) -> bool:
        with log_context(logging.DEBUG, msg=f"received {new_websocket=}"):
            return bool(re.search("/api/kernels/[^/]+/channels", new_websocket.url))


@dataclass(frozen=True)
class _ServiceStepParams:
    page: Page
    websocket: RobustWebSocket
    is_autoscaled: bool
    product_url: AnyUrl
    is_service_legacy: bool
    is_product_lite: bool


def _run_electrode_selector_step(
    params: _ServiceStepParams,
    node_id: str,
    log_ctx: SimpleNamespace,
) -> None:
    electrode_selector_iframe = wait_for_service_running(
        page=params.page,
        node_id=node_id,
        websocket=params.websocket,
        timeout=(
            _ELECTRODE_SELECTOR_AUTOSCALED_MAX_STARTUP_TIME
            if params.is_autoscaled
            else _ELECTRODE_SELECTOR_MAX_STARTUP_TIME
        ),
        press_start_button=False,
        product_url=params.product_url,
        is_service_legacy=params.is_service_legacy,
    )
    params.page.wait_for_timeout(_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME)

    with log_context(logging.INFO, "Configure selector", logger=log_ctx.logger):
        assert params.page.get_by_test_id("settingsForm_" + node_id).count() == 0, (
            "service settings should not be visible"
        )

        electrode_selector_iframe.get_by_test_id("TargetStructure_Selector").click()
        electrode_selector_iframe.get_by_test_id("TargetStructure_Target_(Targets_combined) Hypothalamus").click()
        electrode_selections = [
            ["E1+", "FT9"],
            ["E1-", "FT7"],
            ["E2+", "T9"],
            ["E2-", "T7"],
        ]
        for selection in electrode_selections:
            group_id = "ElectrodeGroup_" + selection[0] + "_Start"
            electrode_id = "Electrode_" + selection[1]
            electrode_selector_iframe.get_by_test_id(group_id).click()
            electrode_selector_iframe.get_by_test_id(electrode_id).click()
    # configuration done, push and wait for the 1 output
    with log_context(logging.INFO, "Check outputs", logger=log_ctx.logger):
        waiter = SocketIOWaitNodeForOutputs(expected_number_of_outputs=1, node_id=node_id)
        with params.websocket.expect_event("framereceived", waiter) as frame_received_event:
            electrode_selector_iframe.get_by_test_id("FinishSetUp").click()
        socket_io_message = decode_socketio_42_message(frame_received_event.value)
        log_ctx.logger.info(
            "the following output was generated: %s",
            socket_io_message.obj["data"]["outputs"]["output_1"]["path"],
        )


def _run_classic_ti_step(
    params: _ServiceStepParams,
    node_id: str,
    log_ctx: SimpleNamespace,
) -> RobustWebSocket:
    with params.page.expect_websocket(
        _JLabWaitForWebSocket(),
        timeout=_OUTER_EXPECT_TIMEOUT_RATIO
        * (POST_PRO_AUTOSCALED_MAX_STARTUP_TIME if params.is_autoscaled else POST_PRO_MAX_STARTUP_TIME),
    ) as ws_info:
        ti_postpro_iframe = wait_for_service_running(
            page=params.page,
            node_id=node_id,
            websocket=params.websocket,
            timeout=(POST_PRO_AUTOSCALED_MAX_STARTUP_TIME if params.is_autoscaled else POST_PRO_MAX_STARTUP_TIME),
            press_start_button=False,
            product_url=params.product_url,
            is_service_legacy=params.is_service_legacy,
        )
        assert ti_postpro_iframe

    assert not ws_info.value.is_closed()
    restartable_jlab_websocket = RobustWebSocket(params.page, ws_info.value)

    with log_context(logging.INFO, "Wait for UI to load"):
        wait_and_select_target_tissue(
            ti_postpro_iframe,
            label_timeout=POST_PRO_TARGET_TISSUE_APPEARANCE_TIME,
            select_timeout=POST_PRO_LOAD_APPEARANCE_TIME,
        )

    if params.is_product_lite:
        with log_context(logging.INFO, "Check species selector has only 2 options", logger=log_ctx.logger):
            species_selector = ti_postpro_iframe.locator("select").first
            options = species_selector.locator("option")
            expect(options).to_have_count(2)
            expect(options.nth(0)).to_have_attribute("value", "Human - MIDA anisotropic")
            expect(options.nth(1)).to_have_attribute("value", "Mouse")

    set_fast_optimization_settings(ti_postpro_iframe)

    with log_context(logging.INFO, "Run optimization and load analysis", logger=log_ctx.logger):
        run_optimization_and_load_analysis(
            ti_postpro_iframe,
            click_timeout=POST_PRO_LOAD_APPEARANCE_TIME,
            optimization_timeout=POST_PRO_RUN_OPTIMIZATION_MAX_TIME,
            optimization_start_timeout=POST_PRO_LOAD_APPEARANCE_TIME,
            analysis_timeout=POST_PRO_LOAD_ANALYSIS_MAX_TIME,
            result_timeout=POST_PRO_LOAD_RESULT_MAX_TIME,
        )

    with log_context(logging.INFO, "Create report", logger=log_ctx.logger):
        if params.is_product_lite:
            assert (
                ti_postpro_iframe.get_by_role("button", name="Add to Report (0)").nth(0).get_attribute("disabled")
                is not None
            ), "Add to Report button should be disabled in lite product"
            assert (
                ti_postpro_iframe.get_by_role("button", name="Export to S4L").get_attribute("disabled") is not None
            ), "Export to S4L button should be disabled in lite product"
            assert (
                ti_postpro_iframe.get_by_role("button", name="Export Report").get_attribute("disabled") is not None
            ), "Export Report button should be disabled in lite product"

        else:
            with log_context(
                logging.INFO,
                f"Click button - `Add to Report (0)` and wait for {POST_PRO_REPORTING_MAX_TIME}",
            ):
                ti_postpro_iframe.get_by_role("button", name="Add to Report (0)").nth(0).click()
                params.page.wait_for_timeout(POST_PRO_REPORTING_MAX_TIME)
            with log_context(
                logging.INFO,
                "Click button - `Export to S4L` and wait for spinner",
            ):
                export_s4l_button = ti_postpro_iframe.get_by_role("button", name="Export to S4L")
                export_s4l_button.click()
                wait_for_export_complete(export_s4l_button)
            with log_context(
                logging.INFO,
                f"Click button - `Add to Report (1)` and wait for {POST_PRO_REPORTING_MAX_TIME}",
            ):
                ti_postpro_iframe.get_by_role("button", name="Add to Report (1)").nth(1).click()
                params.page.wait_for_timeout(POST_PRO_REPORTING_MAX_TIME)
            with log_context(
                logging.INFO,
                "Click button - `Export Report` and wait for spinner",
            ):
                export_report_button = ti_postpro_iframe.get_by_role("button", name="Export Report")
                export_report_button.click()
                wait_for_export_complete(export_report_button)

    with log_context(logging.INFO, "Check outputs", logger=log_ctx.logger):
        if params.is_product_lite:
            expected_outputs = ["results.csv", "MIDA_Anisotropic.smash", "WM.cache"]
            text_on_output_button = f"Outputs ({len(expected_outputs)})"
            params.page.get_by_test_id("outputsBtn").get_by_text(text_on_output_button).click()

        else:
            expected_outputs = ["output_1.zip", "TIP_report.pdf", "results.csv", "MIDA_Anisotropic.smash", "WM.cache"]
            text_on_output_button = f"Outputs ({len(expected_outputs)})"
            params.page.get_by_test_id("outputsBtn").get_by_text(text_on_output_button).click()

    return restartable_jlab_websocket


def _run_exposure_analysis_step(
    params: _ServiceStepParams,
    node_id: str,
    log_ctx: SimpleNamespace,
) -> None:
    with expected_service_running(
        page=params.page,
        node_id=node_id,
        websocket=params.websocket,
        timeout=(POST_PRO_AUTOSCALED_MAX_STARTUP_TIME if params.is_autoscaled else POST_PRO_MAX_STARTUP_TIME),
        press_start_button=False,
        product_url=params.product_url,
        is_service_legacy=params.is_service_legacy,
    ) as service_running:
        app_mode_trigger_next_app(params.page)
    s4l_postpro_iframe = service_running.iframe_locator
    assert s4l_postpro_iframe


def test_classic_ti_plan(
    page: Page,
    log_in_and_out: RobustWebSocket,
    is_autoscaled: bool,
    is_product_lite: bool,
    create_tip_plan_from_dashboard: Callable[[str], dict[str, Any]],
    product_url: AnyUrl,
    is_service_legacy: bool,
    playwright_test_results_dir: Path,
):
    with log_context(logging.INFO, "Checking 'Access TIP' teaser"):
        # click to open and expand
        page.get_by_test_id("userMenuBtn").click()

        if is_product_lite:
            page.get_by_test_id("userMenuAccessTIPBtn").click()
            assert page.get_by_test_id("tipTeaserWindow").is_visible()
            page.get_by_test_id("tipTeaserWindowCloseBtn").click()
        else:
            assert page.get_by_test_id("userMenuAccessTIPBtn").count() == 0, "full version should NOT have a teaser"
            # click to close
            page.get_by_test_id("userMenuBtn").click()

    # press + button
    project_data = create_tip_plan_from_dashboard("newTIPlanButton")
    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(project_data["workbench"], dict), "Expected workbench to be a dict!"
    workbench: dict = project_data["workbench"]

    # count the number of elements with test id matching the pattern
    # 1. Classic TI (ti-postpro)
    # 2. Exposure Analysis (sim4life-postpro) - only in full product
    expected_number_of_steps = 2 if not is_product_lite else 1
    assert len(workbench) == expected_number_of_steps, f"Expected {expected_number_of_steps=} in the app-mode"
    step_buttons_count = page.locator("[osparc-test-id^='AppMode_StepBtn_']").count()
    assert step_buttons_count == expected_number_of_steps, (
        f"Expected {expected_number_of_steps=} visible in the app-mode, got {step_buttons_count=}"
    )

    params = _ServiceStepParams(
        page=page,
        websocket=log_in_and_out,
        is_autoscaled=is_autoscaled,
        product_url=product_url,
        is_service_legacy=is_service_legacy,
        is_product_lite=is_product_lite,
    )

    with log_context(logging.INFO, "Classic TI step (1/%s)", expected_number_of_steps) as log_ctx:
        classic_ti_node_id = get_node_id_from_service_key(workbench, "simcore/services/dynamic/ti-postpro")
        restartable_jlab_websocket = _run_classic_ti_step(params, classic_ti_node_id, log_ctx)

    if is_product_lite:
        assert expected_number_of_steps == 1
    else:
        with log_context(logging.INFO, "Exposure Analysis step (2/%s)", expected_number_of_steps) as log_ctx:
            exposure_analysis_node_id = get_node_id_from_service_key(workbench, "simcore/services/dynamic/s4l-ui")
            _run_exposure_analysis_step(params, exposure_analysis_node_id, log_ctx)

    restartable_jlab_websocket.auto_reconnect = False
