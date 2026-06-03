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

from playwright.sync_api import Page, PlaywrightError, WebSocket, expect
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
from tenacity import RetryError, retry, stop_after_delay, wait_fixed

_OUTER_EXPECT_TIMEOUT_RATIO: Final[float] = 1.1
_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE

_ELECTRODE_SELECTOR_MAX_STARTUP_TIME: Final[int] = 2 * MINUTE
_ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME: Final[int] = 3 * MINUTE
_ELECTRODE_SELECTOR_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME + _ELECTRODE_SELECTOR_MAX_STARTUP_TIME
)
_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME: Final[int] = 5 * SECOND


_JLAB_MAX_STARTUP_MAX_TIME: Final[int] = 5 * MINUTE
_JLAB_DOCKER_PULLING_MAX_TIME: Final[int] = 15 * MINUTE
_JLAB_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _JLAB_DOCKER_PULLING_MAX_TIME + _JLAB_MAX_STARTUP_MAX_TIME
)
_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME: Final[int] = 2 * MINUTE
_JLAB_RUN_OPTIMIZATION_MAX_TIME: Final[int] = 20 * MINUTE
_JLAB_EXPORTING_MAX_TIME: Final[int] = 2 * MINUTE
_JLAB_REPORTING_MAX_TIME: Final[int] = 60 * SECOND


_POST_PRO_MAX_STARTUP_TIME: Final[int] = 5 * MINUTE
_POST_PRO_DOCKER_PULLING_MAX_TIME: Final[int] = 15 * MINUTE
_POST_PRO_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _POST_PRO_DOCKER_PULLING_MAX_TIME + _POST_PRO_MAX_STARTUP_TIME
)


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


@retry(
    stop=stop_after_delay(_JLAB_RUN_OPTIMIZATION_MAX_TIME / 1000),  # seconds
    wait=wait_fixed(10),
    reraise=True,
)
def _wait_for_optimization_complete(run_button) -> None:
    if not run_button.is_enabled():
        msg = f"Optimization not finished yet: {run_button=}"
        raise ValueError(msg)


@retry(
    stop=stop_after_delay(_JLAB_EXPORTING_MAX_TIME / 1000),  # seconds
    wait=wait_fixed(10),
    reraise=True,
)
def _wait_for_export_complete(button) -> None:
    """Wait for an export button to finish by checking the fa-spinner icon."""
    try:
        icon_class = button.locator("i").first.evaluate("el => el.className")
    except PlaywrightError:
        logging.info("Export button icon not found — export likely completed")
        return
    if "fa-spinner" in icon_class:
        msg = f"Export still running: {icon_class=}"
        raise ValueError(msg)


def _run_classic_ti_step(  # noqa: PLR0915
    params: _ServiceStepParams,
    node_id: str,
    log_ctx: SimpleNamespace,
) -> RobustWebSocket:
    with params.page.expect_websocket(
        _JLabWaitForWebSocket(),
        timeout=_OUTER_EXPECT_TIMEOUT_RATIO
        * (_JLAB_AUTOSCALED_MAX_STARTUP_TIME if params.is_autoscaled else _JLAB_MAX_STARTUP_MAX_TIME),
    ) as ws_info:
        ti_iframe = wait_for_service_running(
            page=params.page,
            node_id=node_id,
            websocket=params.websocket,
            timeout=(_JLAB_AUTOSCALED_MAX_STARTUP_TIME if params.is_autoscaled else _JLAB_MAX_STARTUP_MAX_TIME),
            press_start_button=False,
            product_url=params.product_url,
            is_service_legacy=params.is_service_legacy,
        )
        assert ti_iframe

    assert not ws_info.value.is_closed()
    restartable_jlab_websocket = RobustWebSocket(params.page, ws_info.value)

    with log_context(logging.INFO, "Wait for UI to load"):
        target_tissue_label = ti_iframe.get_by_text("Target tissue:")
        expect(target_tissue_label).to_be_visible(timeout=_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME)

    with log_context(logging.INFO, "Select Target tissue"):
        target_tissue_select = ti_iframe.get_by_label("Target tissue")
        expect(target_tissue_select).to_be_visible()
        # Pick the first non-empty option
        options = target_tissue_select.locator("option").all()
        selected = False
        for option in options:
            value = option.get_attribute("value") or ""
            if value.strip():
                target_tissue_select.select_option(value=value)
                logging.info("Selected target tissue: %s", option.inner_text())
                selected = True
                break
        assert selected, "No non-empty target tissue option found"

    if params.is_product_lite:
        with log_context(logging.INFO, "Check species selector has only 2 options", logger=log_ctx.logger):
            species_selector = ti_iframe.locator("select").first
            options = species_selector.locator("option")
            expect(options).to_have_count(2)
            expect(options.nth(0)).to_have_attribute("value", "Human - MIDA anisotropic")
            expect(options.nth(1)).to_have_attribute("value", "Mouse")

    with log_context(logging.INFO, "Run optimization", logger=log_ctx.logger) as ctx2:
        run_button = ti_iframe.get_by_role("button", name="Run Optimization")
        run_button.click()
        try:
            expect(run_button).to_be_disabled(timeout=_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME)
            _wait_for_optimization_complete(run_button)
            ctx2.logger.info("Optimization finished!")
        except RetryError as e:
            last_exc = e.last_attempt.exception()
            ctx2.logger.warning("Optimization did not finish in time: %s", f"{last_exc}")

    with log_context(logging.INFO, "Create report", logger=log_ctx.logger):
        with log_context(
            logging.INFO,
            f"Click button - `Load Analysis` and wait for {_JLAB_REPORTING_MAX_TIME}",
        ):
            ti_iframe.get_by_role("button", name="Load Analysis").click()
            params.page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)
        with log_context(
            logging.INFO,
            f"Click button - `Load` and wait for {_JLAB_REPORTING_MAX_TIME}",
        ):
            ti_iframe.get_by_role("button", name="Load").nth(1).click()
            params.page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)

        if params.is_product_lite:
            assert (
                ti_iframe.get_by_role("button", name="Add to Report (0)").nth(0).get_attribute("disabled") is not None
            ), "Add to Report button should be disabled in lite product"
            assert ti_iframe.get_by_role("button", name="Export to S4L").get_attribute("disabled") is not None, (
                "Export to S4L button should be disabled in lite product"
            )
            assert ti_iframe.get_by_role("button", name="Export Report").get_attribute("disabled") is not None, (
                "Export Report button should be disabled in lite product"
            )

        else:
            with log_context(
                logging.INFO,
                f"Click button - `Add to Report (0)` and wait for {_JLAB_REPORTING_MAX_TIME}",
            ):
                ti_iframe.get_by_role("button", name="Add to Report (0)").nth(0).click()
                params.page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)
            with log_context(
                logging.INFO,
                "Click button - `Export to S4L` and wait for spinner",
            ):
                export_s4l_button = ti_iframe.get_by_role("button", name="Export to S4L")
                export_s4l_button.click()
                _wait_for_export_complete(export_s4l_button)
            with log_context(
                logging.INFO,
                f"Click button - `Add to Report (1)` and wait for {_JLAB_REPORTING_MAX_TIME}",
            ):
                ti_iframe.get_by_role("button", name="Add to Report (1)").nth(1).click()
                params.page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)
            with log_context(
                logging.INFO,
                "Click button - `Export Report` and wait for spinner",
            ):
                export_report_button = ti_iframe.get_by_role("button", name="Export Report")
                export_report_button.click()
                _wait_for_export_complete(export_report_button)

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
        timeout=(_POST_PRO_AUTOSCALED_MAX_STARTUP_TIME if params.is_autoscaled else _POST_PRO_MAX_STARTUP_TIME),
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
    node_ids: list[str] = list(project_data["workbench"])

    # count the number of elements with test id matching the pattern
    # 1. Classic TI (ti-postpro)
    # 2. Exposure Analysis (sim4life-postpro) - only in full product
    expected_number_of_steps = 2 if not is_product_lite else 1
    assert len(node_ids) == expected_number_of_steps, f"Expected {expected_number_of_steps=} in the app-mode"
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
        restartable_jlab_websocket = _run_classic_ti_step(params, node_ids[0], log_ctx)

    if is_product_lite:
        assert expected_number_of_steps == 1
    else:
        with log_context(logging.INFO, "Exposure Analysis step (2/%s)", expected_number_of_steps) as log_ctx:
            _run_exposure_analysis_step(params, node_ids[1], log_ctx)

    restartable_jlab_websocket.auto_reconnect = False
