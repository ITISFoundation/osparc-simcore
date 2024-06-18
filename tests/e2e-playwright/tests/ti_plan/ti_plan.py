# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import pytest
from playwright.sync_api import APIRequestContext, Page, Request, WebSocket, expect
from pydantic import AnyUrl
from pytest_simcore.logging_utils import log_context
from pytest_simcore.playwright_utils import RunningState
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


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
        confirm_open = False
        return create_new_project_and_delete(expected_states, confirm_open)

    return _


_LET_IT_START_OR_FORCE_WAIT_TIME_MS: Final[int] = 5000
_ELECTRODE_SELECTOR_FLICKERING_WAIT_TIME_MS: Final[int] = 5000
_NODE_START_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"/projects/[^/]+/nodes/[^:]+:start"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class _RequestPredicate:
    url_pattern: re.Pattern[str] | str
    method: str

    def __call__(self, request: Request) -> bool:
        return bool(
            re.search(self.url_pattern, request.url)
            and request.method.upper() == self.method.upper()
        )

    def __post_init__(self) -> None:
        if not isinstance(self.url_pattern, re.Pattern):
            object.__setattr__(self, "url_pattern", re.compile(self.url_pattern))


def _wait_or_force_start_service(
    page: Page, logger: logging.Logger, node_id: str, *, press_next: bool
) -> None:
    try:
        with page.expect_request(
            _RequestPredicate(url_pattern=_NODE_START_PATTERN, method="POST")
        ):
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
        with page.expect_request(
            _RequestPredicate(url_pattern=_NODE_START_PATTERN, method="POST")
        ):
            page.get_by_test_id(f"Start_{node_id}").click()


_JLAB_STARTUP_MAX_TIME: Final[int] = 60 * 1000


@dataclass
class _JLabWaitForWebSocket:
    def __call__(self, new_websocket: WebSocket) -> bool:
        with log_context(logging.DEBUG, msg=f"received {new_websocket=}"):
            if re.search(r"/api/kernels/[^/]+/channels", new_websocket.url):
                return True
            return False


@dataclass
class _JLabWebSocketWaiter:
    # expected_message_type: Literal["stdout", "stdin"]
    # expected_message_contents: str

    def __call__(self, message: str) -> bool:
        with log_context(logging.INFO, msg=f"handling websocket {message=}"):
            # decoded_message = json.loads(message)
            # if (
            #     self.expected_message_type == decoded_message[0]
            #     and self.expected_message_contents in decoded_message[1]
            # ):
            #     return True

            return False


def test_tip(
    page: Page,
    create_tip_plan_from_dashboard: Callable[[str], dict[str, Any]],
    log_in_and_out: WebSocket,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
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
        _wait_or_force_start_service(page, ctx.logger, node_ids[0], press_next=False)

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
        # configuration done, push output
        with page.expect_request(
            _RequestPredicate(
                method="GET", url_pattern=r"/storage/locations/[^/]+/files"
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
            _JLabWaitForWebSocket(), timeout=_JLAB_STARTUP_MAX_TIME
        ) as ws_info:
            _wait_or_force_start_service(page, ctx.logger, node_ids[1], press_next=True)
        jlab_websocket = ws_info.value

        # Optimal Configuration Identification
        ti_page = page.frame_locator(f'[osparc-test-id="iframe_{node_ids[1]}"]')
        run_button_locator = ti_page.get_by_role("button", name="Run Optimization")
        try:
            expect(run_button_locator).to_be_visible()
        except AssertionError:
            ctx.error("Classic TI failed to start, trying to restart the iFrame...")
            with page.expect_websocket(
                _JLabWaitForWebSocket(), timeout=_JLAB_STARTUP_MAX_TIME
            ) as ws_info:
                page.get_by_test_id("iFrameRestartBtn").click()
            jlab_websocket = ws_info.value

        with jlab_websocket.expect_event("framereceived", _JLabWebSocketWaiter()):
            run_button = ti_page.get_by_role(
                "button", name=re.compile("Run Optimization", re.IGNORECASE)
            ).click()

        # TODO: we can wait here for the wssocket msg["header"]["msg_type"] == "stream" that msg["content"]["text"] contains "All results evaluated"
        for attempt in Retrying(
            wait=wait_fixed(5),
            stop=stop_after_attempt(20),  # 5*20= 100 seconds
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
        ):
            with attempt:
                # When optimization finishes, the button changes color.
                _run_button_style = run_button.evaluate(
                    "el => window.getComputedStyle(el)"
                )
                assert (
                    _run_button_style["backgroundColor"] == "rgb(0, 128, 0)"
                )  # initial color: rgb(0, 144, 208)

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
        _wait_or_force_start_service(page, ctx.logger, node_ids[2], press_next=True)

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
