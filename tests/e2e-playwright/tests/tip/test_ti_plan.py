# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import contextlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from playwright.sync_api import Page, WebSocket
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    RestartableWebSocket,
    app_mode_trigger_next_app,
    expected_service_running,
    wait_for_service_running,
)

_GET_NODE_OUTPUTS_REQUEST_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"/storage/locations/[^/]+/files"
)
_OUTER_EXPECT_TIMEOUT_RATIO: Final[float] = 1.1
_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE

_ELECTRODE_SELECTOR_MAX_STARTUP_TIME: Final[int] = 1 * MINUTE
_ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME: Final[int] = 3 * MINUTE
_ELECTRODE_SELECTOR_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME
    + _ELECTRODE_SELECTOR_DOCKER_PULLING_MAX_TIME
    + _ELECTRODE_SELECTOR_MAX_STARTUP_TIME
)
_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME: Final[int] = 5 * SECOND


_JLAB_MAX_STARTUP_MAX_TIME: Final[int] = 3 * MINUTE
_JLAB_DOCKER_PULLING_MAX_TIME: Final[int] = 12 * MINUTE
_JLAB_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME
    + _JLAB_DOCKER_PULLING_MAX_TIME
    + _JLAB_MAX_STARTUP_MAX_TIME
)
_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME: Final[int] = 2 * MINUTE
_JLAB_RUN_OPTIMIZATION_MAX_TIME: Final[int] = 4 * MINUTE
_JLAB_REPORTING_MAX_TIME: Final[int] = 60 * SECOND


_POST_PRO_MAX_STARTUP_TIME: Final[int] = 2 * MINUTE
_POST_PRO_DOCKER_PULLING_MAX_TIME: Final[int] = 12 * MINUTE
_POST_PRO_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME
    + _POST_PRO_DOCKER_PULLING_MAX_TIME
    + _POST_PRO_MAX_STARTUP_TIME
)


@dataclass
class _JLabWaitForWebSocket:
    def __call__(self, new_websocket: WebSocket) -> bool:
        with log_context(logging.DEBUG, msg=f"received {new_websocket=}"):
            return bool(re.search("/api/kernels/[^/]+/channels", new_websocket.url))


@dataclass
class _JLabWebSocketWaiter:
    expected_header_msg_type: str
    expected_message_contents: str

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}"):
            with contextlib.suppress(json.JSONDecodeError, UnicodeDecodeError):
                decoded_message = json.loads(message)
                msg_type: str = decoded_message.get("header", {}).get("msg_type", "")
                msg_contents: str = decoded_message.get("content", {}).get("text", "")
                if (msg_type == self.expected_header_msg_type) and (
                    self.expected_message_contents in msg_contents
                ):
                    return True

            return False


def test_classic_ti_plan(  # noqa: PLR0915
    page: Page,
    log_in_and_out: RestartableWebSocket,
    is_autoscaled: bool,
    is_product_lite: bool,
    create_tip_plan_from_dashboard: Callable[[str], dict[str, Any]],
    product_url: AnyUrl,
):
    with log_context(logging.INFO, "Checking 'Access TIP' teaser"):
        # click to open and expand
        page.get_by_test_id("userMenuBtn").click()

        if is_product_lite:
            page.get_by_test_id("userMenuAccessTIPBtn").click()
            assert page.get_by_test_id("tipTeaserWindow").is_visible()
            page.get_by_test_id("tipTeaserWindowCloseBtn").click()
        else:
            assert (
                page.get_by_test_id("userMenuAccessTIPBtn").count() == 0
            ), "full version should NOT have a teaser"
            # click to close
            page.get_by_test_id("userMenuBtn").click()

    # press + button
    project_data = create_tip_plan_from_dashboard("newTIPlanButton")
    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(
        project_data["workbench"], dict
    ), "Expected workbench to be a dict!"
    node_ids: list[str] = list(project_data["workbench"])

    if is_product_lite:
        expected_number_of_steps = 2
        assert (
            len(node_ids) == expected_number_of_steps
        ), f"Expected {expected_number_of_steps=} in the app-mode"
    else:
        expected_number_of_steps = 3
        assert (
            len(node_ids) >= expected_number_of_steps
        ), f"Expected at least {expected_number_of_steps} nodes in the workbench"

    with log_context(
        logging.INFO, "Electrode Selector step (1/%s)", expected_number_of_steps
    ) as ctx:
        # NOTE: creating the plan auto-triggers the first service to start, which might already triggers socket events
        electrode_selector_iframe = wait_for_service_running(
            page=page,
            node_id=node_ids[0],
            websocket=log_in_and_out,
            timeout=(
                _ELECTRODE_SELECTOR_AUTOSCALED_MAX_STARTUP_TIME
                if is_autoscaled
                else _ELECTRODE_SELECTOR_MAX_STARTUP_TIME
            ),
            press_start_button=False,
            product_url=product_url,
        )
        # NOTE: Sometimes this iframe flicks and shows a white page. This wait will avoid it
        page.wait_for_timeout(_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME)

        with log_context(logging.INFO, "Configure selector"):
            electrode_selector_iframe.get_by_test_id("TargetStructure_Selector").click()
            electrode_selector_iframe.get_by_test_id(
                "TargetStructure_Target_(Targets_combined) Hypothalamus"
            ).click()
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
        # configuration done, push and wait for output
        with (
            log_context(logging.INFO, "Check outputs"),
            page.expect_request(
                lambda r: bool(
                    re.search(_GET_NODE_OUTPUTS_REQUEST_PATTERN, r.url)
                    and r.method.upper() == "GET"
                )
            ) as request_info,
        ):
            electrode_selector_iframe.get_by_test_id("FinishSetUp").click()
            response = request_info.value.response()
            assert response
            assert response.ok, f"{response.json()}"
            response_body = response.json()
            ctx.logger.info("the following output was generated: %s", response_body)

    with log_context(
        logging.INFO, "Classic TI step (2/%s)", expected_number_of_steps
    ) as ctx:
        with page.expect_websocket(
            _JLabWaitForWebSocket(),
            timeout=_OUTER_EXPECT_TIMEOUT_RATIO
            * (
                _JLAB_AUTOSCALED_MAX_STARTUP_TIME
                if is_autoscaled
                else _JLAB_MAX_STARTUP_MAX_TIME
            ),
        ) as ws_info:
            with expected_service_running(
                page=page,
                node_id=node_ids[1],
                websocket=log_in_and_out,
                timeout=(
                    _JLAB_AUTOSCALED_MAX_STARTUP_TIME
                    if is_autoscaled
                    else _JLAB_MAX_STARTUP_MAX_TIME
                ),
                press_start_button=False,
                product_url=product_url,
            ) as service_running:
                app_mode_trigger_next_app(page)
            ti_iframe = service_running.iframe_locator
            assert ti_iframe

        assert not ws_info.value.is_closed()
        restartable_jlab_websocket = RestartableWebSocket.create(page, ws_info.value)

        with (
            log_context(logging.INFO, "Run optimization"),
            restartable_jlab_websocket.expect_event(
                "framereceived",
                _JLabWebSocketWaiter(
                    expected_header_msg_type="stream",
                    expected_message_contents="All results evaluated",
                ),
                timeout=_JLAB_RUN_OPTIMIZATION_MAX_TIME
                + _JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME,
            ),
        ):
            ti_iframe.get_by_role("button", name="Run Optimization").click(
                timeout=_JLAB_RUN_OPTIMIZATION_APPEARANCE_TIME
            )

        with log_context(logging.INFO, "Create report"):
            with log_context(
                logging.INFO,
                f"Click button - `Load Analysis` and wait for {_JLAB_REPORTING_MAX_TIME}",
            ):
                ti_iframe.get_by_role("button", name="Load Analysis").click()
                page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)
            with log_context(
                logging.INFO,
                f"Click button - `Load` and wait for {_JLAB_REPORTING_MAX_TIME}",
            ):
                ti_iframe.get_by_role("button", name="Load").nth(1).click()
                page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)

            if is_product_lite:
                assert (
                    not ti_iframe.get_by_role("button", name="Add to Report (0)")
                    .nth(0)
                    .is_enabled()
                )
                assert not ti_iframe.get_by_role(
                    "button", name="Export to S4L"
                ).is_enabled()
                assert not ti_iframe.get_by_role(
                    "button", name="Export Report"
                ).is_enabled()

            else:
                with log_context(
                    logging.INFO,
                    f"Click button - `Add to Report (0)` and wait for {_JLAB_REPORTING_MAX_TIME}",
                ):
                    ti_iframe.get_by_role("button", name="Add to Report (0)").nth(
                        0
                    ).click()
                    page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)
                with log_context(
                    logging.INFO,
                    f"Click button - `Export to S4L` and wait for {_JLAB_REPORTING_MAX_TIME}",
                ):
                    ti_iframe.get_by_role("button", name="Export to S4L").click()
                    page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)
                with log_context(
                    logging.INFO,
                    f"Click button - `Add to Report (1)` and wait for {_JLAB_REPORTING_MAX_TIME}",
                ):
                    ti_iframe.get_by_role("button", name="Add to Report (1)").nth(
                        1
                    ).click()
                    page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)
                with log_context(
                    logging.INFO,
                    f"Click button - `Export Report` and wait for {_JLAB_REPORTING_MAX_TIME}",
                ):
                    ti_iframe.get_by_role("button", name="Export Report").click()
                    page.wait_for_timeout(_JLAB_REPORTING_MAX_TIME)

        with log_context(logging.INFO, "Check outputs"):
            if is_product_lite:
                expected_outputs = ["results.csv"]
                text_on_output_button = f"Outputs ({len(expected_outputs)})"
                page.get_by_test_id("outputsBtn").get_by_text(
                    text_on_output_button
                ).click()

            else:
                expected_outputs = ["output_1.zip", "TIP_report.pdf", "results.csv"]
                text_on_output_button = f"Outputs ({len(expected_outputs)})"
                page.get_by_test_id("outputsBtn").get_by_text(
                    text_on_output_button
                ).click()

    if is_product_lite:
        assert expected_number_of_steps == 2
    else:
        with log_context(
            logging.INFO, "Exposure Analysis step (3/%s)", expected_number_of_steps
        ):
            with expected_service_running(
                page=page,
                node_id=node_ids[2],
                websocket=log_in_and_out,
                timeout=(
                    _POST_PRO_AUTOSCALED_MAX_STARTUP_TIME
                    if is_autoscaled
                    else _POST_PRO_MAX_STARTUP_TIME
                ),
                press_start_button=False,
                product_url=product_url,
            ) as service_running:
                app_mode_trigger_next_app(page)
            s4l_postpro_iframe = service_running.iframe_locator
            assert s4l_postpro_iframe

            with log_context(logging.INFO, "Post process"):
                # click on the postpro mode button
                s4l_postpro_iframe.get_by_test_id("mode-button-postro").click()
                # click on the surface viewer
                s4l_postpro_iframe.get_by_test_id("tree-item-ti_field.cache").click()
                s4l_postpro_iframe.get_by_test_id("tree-item-SurfaceViewer").nth(
                    0
                ).click()
