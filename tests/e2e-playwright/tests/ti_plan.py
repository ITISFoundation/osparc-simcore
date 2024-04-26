# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import re
from http import HTTPStatus

from playwright.sync_api import APIRequestContext, Page, WebSocket, expect
from pydantic import AnyUrl
from pytest_simcore.playwright_utils import SocketIOOsparcMessagePrinter
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


def test_tip(
    page: Page,
    log_in_and_out: WebSocket,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    product_billable: bool,
):
    handler = SocketIOOsparcMessagePrinter()
    # log_in_and_out is the initial websocket
    log_in_and_out.on("framereceived", handler)

    # open studies tab and filter
    page.get_by_test_id("studiesTabBtn").click()
    _textbox = page.get_by_test_id("searchBarFilter-textField-study")
    _textbox.fill("Classic TI")
    _textbox.press("Enter")

    with page.expect_response(re.compile(r"/projects/[^:]+:open")) as response_info:
        page.get_by_test_id("newTIPlanButton").click()
        if product_billable:
            # Open project with default resources
            page.get_by_test_id("openWithResources").click()
        page.wait_for_timeout(1000)

    project_data = response_info.value.json()
    assert project_data
    project_uuid = project_data["data"]["uuid"]
    print("project uuid: ", project_uuid)
    node_ids = []
    for node_id in project_data["data"]["workbench"].keys():
        print("node_id: ", node_id)
        node_ids.append(node_id)

    # let it start or force
    page.wait_for_timeout(5000)
    start_button = page.get_by_test_id("Start_" + node_ids[0])
    if start_button.is_visible() and start_button.is_enabled():
        start_button.click()

    # Electrode Selector
    es_page = page.frame_locator(f'[osparc-test-id="iframe_{node_ids[0]}"]')
    expect(es_page.get_by_test_id("TargetStructure_Selector")).to_be_visible(
        timeout=300000
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

    # let it start or force
    page.wait_for_timeout(5000)
    start_button = page.get_by_test_id("Start_" + node_ids[1])
    if start_button.is_visible() and start_button.is_enabled():
        start_button.click()

    # Optimal Configuration Identification
    ti_page = page.frame_locator(f'[osparc-test-id="iframe_{node_ids[1]}"]')
    expect(ti_page.get_by_role("button", name="Run Optimization")).to_be_visible(
        timeout=300000
    )
    ti_page.get_by_role("button", name="Run Optimization").click()
    page.wait_for_timeout(20000)
    ti_page.get_by_role("button", name="Load Analysis").click()
    page.wait_for_timeout(20000)
    ti_page.get_by_role("button", name="Load").nth(1).click()  # Load Analysis is first
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

    # let it start or force
    page.wait_for_timeout(5000)
    start_button = page.get_by_test_id("Start_ " + node_ids[2])
    if start_button.is_visible() and start_button.is_enabled():
        start_button.click()

    # Sim4Life PostPro
    s4l_postpro_page = page.frame_locator(f'[osparc-test-id="iframe_{node_ids[2]}"]')
    expect(s4l_postpro_page.get_by_test_id("mode-button-postro")).to_be_visible(
        timeout=300000
    )
    # click on the postpro mode button
    s4l_postpro_page.get_by_test_id("mode-button-postro").click()
    # click on the surface viewer
    s4l_postpro_page.get_by_test_id("tree-item-ti_field.cache").click()
    s4l_postpro_page.get_by_test_id("tree-item-SurfaceViewer").click()
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
