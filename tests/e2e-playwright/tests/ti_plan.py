# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import re
from typing import Final

from playwright.sync_api import APIRequestContext, Page
from pydantic import AnyUrl
from pytest_simcore.playwright_utils import on_web_socket_default_handler

projects_uuid_pattern: Final[re.Pattern] = re.compile(
    r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def test_tip(
    page: Page,
    log_in_and_out: None,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
):
    # connect and listen to websocket
    page.on("websocket", on_web_socket_default_handler)

    # open studies tab and filter
    page.get_by_test_id("studiesTabBtn").click()
    _textbox = page.get_by_test_id("searchBarFilter-textField-study")
    _textbox.fill("Classic TI")
    _textbox.press("Enter")

    with page.expect_response(re.compile(r"/projects/[^:]+:open")) as response_info:
        page.get_by_test_id("newTIPlanButton").click()
        page.wait_for_timeout(1000)

    project_data = response_info.value.json()
    assert project_data
    project_uuid = project_data["data"]["uuid"]
    print("project uuid: ", project_uuid)
    node_ids = []
    for node_id in project_data["data"]["workbench"].keys():
        print("node_id: ", node_id)
        node_ids.append(node_id)

    # Check there are 3 steps

    # Start button might need to be pressed

    # Electrode Selector
    page.wait_for_timeout(30000)
    es_page = page.frame_locator(".qx-main-dark").nth(0)
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
    es_page.get_by_test_id("FinishSetUp").click()
    page.wait_for_timeout(10000)
    # check outputs
    expected_outputs = ["output.json"]
    text_on_output_button = f"Outputs ({len(expected_outputs)})"
    page.get_by_test_id("outputsBtn").get_by_text(text_on_output_button).click()
    page.wait_for_timeout(5000)

    # Move to next step
    page.get_by_test_id("AppMode_NextBtn").click()

    # Optimal Configuration Identification
    page.wait_for_timeout(120000)
    ti_page = page.frame_locator(".qx-main-dark").nth(1)
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

    # Sim4Life PostPro
    page.wait_for_timeout(60000)
    s4l_postpro_page = page.frame_locator(".qx-main-dark").nth(2)
    # make sure there is something in the postpro algorithm tree
    # click on the mode button
    s4l_postpro_page.get_by_test_id("mode-button-postro").click()
    page.wait_for_timeout(5000)
    # click on the surface viewer
    s4l_postpro_page.get_by_test_id("tree-item-ti_field.cache").click()
    s4l_postpro_page.get_by_test_id("tree-item-SurfaceViewer").click()
    page.wait_for_timeout(5000)
