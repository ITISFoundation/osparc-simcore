# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import contextlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import pytest
from playwright.sync_api import Page, Request, WebSocket, expect
from pytest_simcore.logging_utils import log_context
from pytest_simcore.playwright_utils import (
    RunningState,
    SocketIONodeProgressCompleteWaiter,
)


@pytest.fixture
def find_and_start_tip_plan_in_dashboard(
    page: Page,
) -> Callable[[str], None]:
    def _(
        plan_name_test_id: str,
    ) -> None:
        with log_context(logging.INFO, f"Finding {plan_name_test_id=} in dashboard"):
            page.get_by_test_id("studiesTabBtn").click()
            page.get_by_test_id("newStudyBtn").click()
            page.get_by_test_id(plan_name_test_id).click()

    return _


@pytest.fixture
def create_tip_plan_from_dashboard(
    find_and_start_tip_plan_in_dashboard: Callable[[str], None],
    create_new_project_and_delete: Callable[
        [tuple[RunningState], bool], dict[str, Any]
    ],
) -> Callable[[str], dict[str, Any]]:
    def _(plan_name_test_id: str) -> dict[str, Any]:
        find_and_start_tip_plan_in_dashboard(plan_name_test_id)
        expected_states = (RunningState.UNKNOWN,)
        return create_new_project_and_delete(expected_states, press_open=False)

    return _


_SECOND_MS: Final[int] = 1000
_MINUTE_MS: Final[int] = 60 * _SECOND_MS
_JLAB_MAX_STARTUP_TIME_MS: Final[int] = 60 * _SECOND_MS
_JLAB_RUN_OPTIMIZATION_MAX_TIME_MS: Final[int] = 60 * _SECOND_MS

_LET_IT_START_OR_FORCE_WAIT_TIME_MS: Final[int] = 5000
_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME_MS: Final[int] = 5000
_NODE_START_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"/projects/[^/]+/nodes/[^:]+:start"
)
_GET_NODE_OUTPUTS_REQUEST_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"/storage/locations/[^/]+/files"
)

_NODE_START_TIME_MS: Final[int] = 5 * _MINUTE_MS


def _node_start_predicate(request: Request) -> bool:
    return bool(
        re.search(_NODE_START_PATTERN, request.url) and request.method.upper() == "POST"
    )


def _wait_or_trigger_service_start(
    page: Page, node_id: str, press_next: bool, *, logger: logging.Logger
) -> None:
    try:
        with page.expect_request(_node_start_predicate):
            # Move to next step (this auto starts the next service)
            if press_next:
                next_button_locator = page.get_by_test_id("AppMode_NextBtn")
                if (
                    next_button_locator.is_visible()
                    and next_button_locator.is_enabled()
                ):
                    page.get_by_test_id("AppMode_NextBtn").click()
    except TimeoutError:
        logger.warning(
            "Request to start service not received after %sms, forcing start",
            _LET_IT_START_OR_FORCE_WAIT_TIME_MS,
        )
        with page.expect_request(_node_start_predicate):
            page.get_by_test_id(f"Start_{node_id}").click()


def _wait_or_force_start_service(
    *,
    page: Page,
    logger: logging.Logger,
    node_id: str,
    press_next: bool,
    websocket: WebSocket,
) -> None:
    waiter = SocketIONodeProgressCompleteWaiter()
    with log_context(
        logging.INFO, msg="Waiting for node to start"
    ), websocket.expect_event("framereceived", waiter, timeout=_NODE_START_TIME_MS):
        _wait_or_trigger_service_start(page, node_id, press_next, logger=logger)


@dataclass
class _JLabWaitForWebSocket:
    def __call__(self, new_websocket: WebSocket) -> bool:
        with log_context(logging.DEBUG, msg=f"received {new_websocket=}"):
            if re.search(r"/api/kernels/[^/]+/channels", new_websocket.url):
                return True
            return False


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


def test_tip(
    page: Page,
    create_tip_plan_from_dashboard: Callable[[str], dict[str, Any]],
    log_in_and_out: WebSocket,
    product_billable: bool,
    service_opening_waiting_timeout: int,
):
    # handler = SocketIOOsparcMessagePrinter()
    # # log_in_and_out is the initial websocket
    # log_in_and_out.on("framereceived", handler)

    # open studies tab and filter
    project_data = create_tip_plan_from_dashboard("newTIPlanButton")
    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(
        project_data["workbench"], dict
    ), "Expected workbench to be a dict!"
    node_ids: list[str] = list(project_data["workbench"])
    assert len(node_ids) >= 3, "Expected at least 3 nodes in the workbench!"

    with log_context(logging.INFO, "Electrode Selector step") as ctx:
        _wait_or_force_start_service(
            page=page,
            logger=ctx.logger,
            node_id=node_ids[0],
            press_next=False,
            websocket=log_in_and_out,
        )

        # Electrode Selector
        electrode_selector_iframe = page.frame_locator(
            f'[osparc-test-id="iframe_{node_ids[0]}"]'
        )
        expect(
            electrode_selector_iframe.get_by_test_id("TargetStructure_Selector")
        ).to_be_visible(timeout=service_opening_waiting_timeout)
        # NOTE: Sometimes this iframe flicks and shows a white page. This wait will avoid it
        page.wait_for_timeout(_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME_MS)
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
        with page.expect_request(
            lambda r: bool(
                re.search(_GET_NODE_OUTPUTS_REQUEST_PATTERN, r.url)
                and r.method.upper() == "GET"
            )
        ) as request_info:
            electrode_selector_iframe.get_by_test_id("FinishSetUp").click()
        response = request_info.value.response()
        assert response
        assert response.ok, f"{response.json()}"
        response_body = response.json()
        ctx.logger.info("the following output was generated: %s", response_body)

    with log_context(logging.INFO, "Classic TI step") as ctx:
        with page.expect_websocket(
            _JLabWaitForWebSocket(), timeout=_JLAB_MAX_STARTUP_TIME_MS
        ) as ws_info:
            _wait_or_force_start_service(
                page=page,
                logger=ctx.logger,
                node_id=node_ids[1],
                press_next=True,
                websocket=log_in_and_out,
            )
        jlab_websocket = ws_info.value

        # Optimal Configuration Identification
        ti_page = page.frame_locator(f'[osparc-test-id="iframe_{node_ids[1]}"]')
        with jlab_websocket.expect_event(
            "framereceived",
            _JLabWebSocketWaiter(
                expected_header_msg_type="stream",
                expected_message_contents="All results evaluated",
            ),
            timeout=_JLAB_RUN_OPTIMIZATION_MAX_TIME_MS,
        ):
            ti_page.get_by_role("button", name="Run Optimization").click()

        ti_page.get_by_role("button", name="Load Analysis").click()
        page.wait_for_timeout(20000)
        ti_page.get_by_role("button", name="Load").nth(
            1
        ).click()  # Load Analysis is first
        page.wait_for_timeout(20000)
        ti_page.get_by_role("button", name="Add to Report (0)").nth(0).click()
        page.wait_for_timeout(20000)
        ti_page.get_by_role("button", name="Export to S4L").click()
        page.wait_for_timeout(20000)
        ti_page.get_by_role("button", name="Add to Report (1)").nth(1).click()
        page.wait_for_timeout(20000)
        ti_page.get_by_role("button", name="Export Report").click()
        page.wait_for_timeout(20000)
        # check outputs
        expected_outputs = ["output_1.zip", "TIP_report.pdf", "results.csv"]
        text_on_output_button = f"Outputs ({len(expected_outputs)})"
        page.get_by_test_id("outputsBtn").get_by_text(text_on_output_button).click()

    with log_context(logging.INFO, "Exposure Analysis step"):
        _wait_or_force_start_service(
            page=page,
            logger=ctx.logger,
            node_id=node_ids[2],
            press_next=True,
            websocket=log_in_and_out,
        )

        # Sim4Life PostPro
        s4l_postpro_page = page.frame_locator(
            f'[osparc-test-id="iframe_{node_ids[2]}"]'
        )
        expect(s4l_postpro_page.get_by_test_id("mode-button-postro")).to_be_visible(
            timeout=service_opening_waiting_timeout
        )
        # click on the postpro mode button
        s4l_postpro_page.get_by_test_id("mode-button-postro").click()
        # click on the surface viewer
        s4l_postpro_page.get_by_test_id("tree-item-ti_field.cache").click()
        s4l_postpro_page.get_by_test_id("tree-item-SurfaceViewer").nth(0).click()
