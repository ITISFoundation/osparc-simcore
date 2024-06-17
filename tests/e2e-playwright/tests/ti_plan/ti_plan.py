# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import logging
from http import HTTPStatus
from typing import Any, Callable

import pytest
from playwright.sync_api import APIRequestContext, Page, WebSocket, expect
from pydantic import AnyUrl
from pytest_simcore.logging_utils import log_context
from pytest_simcore.playwright_utils import RunningState, SocketIOOsparcMessagePrinter
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
            page.get_by_test_id("servicesTabBtn").click()
            page.get_by_test_id("newStudyBtn").click()
            page.get_by_test_id(plan_name_test_id).click()

    return _


@pytest.fixture
def create_tip_plan_from_dashboard(
    find_and_start_tip_plan_in_dashboard: Callable[[str], None],
    create_new_project_and_delete: Callable[[tuple[RunningState]], dict[str, Any]],
) -> Callable[[str], dict[str, Any]]:
    def _(plan_name_test_id: str) -> dict[str, Any]:
        find_and_start_tip_plan_in_dashboard(plan_name_test_id)
        expected_states = (RunningState.UNKNOWN,)
        return create_new_project_and_delete(expected_states)

    return _


def test_tip(
    page: Page,
    create_tip_plan_from_dashboard: Callable[[str], dict[str, Any]],
    log_in_and_out: WebSocket,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    product_billable: bool,
    service_opening_waiting_timeout: int,
):
    handler = SocketIOOsparcMessagePrinter()
    # log_in_and_out is the initial websocket
    log_in_and_out.on("framereceived", handler)

    # open studies tab and filter
    project_data = create_tip_plan_from_dashboard("newTIPlanButton")
    assert "uuid" in project_data
    assert isinstance(project_data["uuid"], str)
    project_uuid = project_data["uuid"]

    assert "workbench" in project_data
    assert isinstance(project_data["workbench"], dict)
    node_ids: list[str] = list(project_data["workbench"])

    # let it start or force
    with log_context(logging.INFO, "Starting with Electrode Selector"):
        start_button = page.get_by_test_id("Start_" + node_ids[0])
        if start_button.is_visible() and start_button.is_enabled():
            start_button.click()

        # Electrode Selector
        es_page = page.frame_locator(f'[osparc-test-id="iframe_{node_ids[0]}"]')
        expect(es_page.get_by_test_id("TargetStructure_Selector")).to_be_visible(
            timeout=service_opening_waiting_timeout
        )
        # Sometimes this iframe flicks and shows a white page. This wait will avoid it
        page.wait_for_timeout(5000)
        es_page.get_by_test_id("TargetStructure_Selector").click()
        es_page.get_by_test_id(
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
            es_page.get_by_test_id(group_id).click()
            es_page.get_by_test_id(electrode_id).click()
        # configuration done, push output
        page.wait_for_timeout(1000)
        es_page.get_by_test_id("FinishSetUp").click()
        page.wait_for_timeout(10000)
        # check outputs
        expected_outputs = ["output.json"]
        text_on_output_button = f"Outputs ({len(expected_outputs)})"
        page.get_by_test_id("outputsBtn").get_by_text(text_on_output_button).click()
        page.wait_for_timeout(5000)

        # Move to next step
        page.get_by_test_id("AppMode_NextBtn").click()

    with log_context(logging.INFO, "Continue with Classic TI"):
        # let it start or force
        page.wait_for_timeout(5000)
        start_button = page.get_by_test_id("Start_" + node_ids[1])
        if start_button.is_visible() and start_button.is_enabled():
            start_button.click()

        # Optimal Configuration Identification
        ti_page = page.frame_locator(f'[osparc-test-id="iframe_{node_ids[1]}"]')
        expect(ti_page.get_by_role("button", name="Run Optimization")).to_be_visible(
            timeout=service_opening_waiting_timeout
        )
        run_button = ti_page.get_by_role("button", name="Run Optimization")
        run_button.click()
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
        page.wait_for_timeout(5000)

        # Move to next step
        page.get_by_test_id("AppMode_NextBtn").click()

    with log_context(logging.INFO, "Continue to Exposure Analysis"):
        # let it start or force
        page.wait_for_timeout(5000)
        start_button = page.get_by_test_id("Start_ " + node_ids[2])
        if start_button.is_visible() and start_button.is_enabled():
            start_button.click()

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
        page.wait_for_timeout(5000)

    # Going back to dashboard
    page.get_by_test_id("dashboardBtn").click()
    page.get_by_test_id("confirmDashboardBtn").click()
    page.wait_for_timeout(1000)

    # Going back to projects/studies view (In Sim4life projects:=studies)
    page.get_by_test_id("studiesTabBtn").click()
    page.wait_for_timeout(1000)

    # The project is closing, wait until it is closed and delete it (currently waits max=5 minutes)
    for attempt in Retrying(
        wait=wait_fixed(5),
        stop=stop_after_attempt(60),  # 5*60= 300 seconds
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            resp = api_request_context.delete(
                f"{product_url}v0/projects/{project_uuid}"
            )
            assert resp.status == HTTPStatus.NO_CONTENT
