import logging
import re
from collections.abc import Callable
from typing import Any, Final

from playwright.sync_api import Page
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    RobustWebSocket,
    ServiceType,
)

_WAITING_FOR_SERVICE_TO_START: Final[int] = 5 * MINUTE
_WAITING_FOR_SERVICE_TO_APPEAR: Final[int] = 2 * MINUTE
_DEFAULT_RESPONSE_TO_WAIT_FOR: Final[re.Pattern] = re.compile(
    r"/flask/list_function_job_collections_for_functionid"
)

_FUNCTION_NAME: Final[str] = "playwright_test_function"


def test_response_surface_modeling(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None, str | None], dict[str, Any]
    ],
    log_in_and_out: RobustWebSocket,
    service_key: str,
    service_version: str | None,
    product_url: AnyUrl,
    is_service_legacy: bool,
):
    # 1. create the initial study with jsonifier
    with log_context(logging.INFO, "Create new study..."):
        jsonifier_project_data = create_project_from_service_dashboard(
            ServiceType.COMPUTATIONAL, "jsonifier", None, service_version
        )
        assert (
            "workbench" in jsonifier_project_data
        ), "Expected workbench to be in project data!"
        assert isinstance(
            jsonifier_project_data["workbench"], dict
        ), "Expected workbench to be a dict!"
        node_ids: list[str] = list(jsonifier_project_data["workbench"])
        assert len(node_ids) == 1, "Expected 1 node in the workbench!"

        # select the jsonifier, it's the second one as the study has the same name
        page.get_by_test_id("nodeTreeItem").filter(has_text="jsonifier").all()[
            1
        ].click()

        # create the probe
        page.get_by_test_id("connect_probe_btn_number_3").click()

        # # create the parameter
        # with page.expect_response(
        #     re.compile(rf"/projects/{jsonifier_project_data['uuid']}/nodes")
        # ):
        #     page.get_by_test_id("newNodeBtn").click()
        #     page.get_by_placeholder("Filter").click()
        #     page.get_by_placeholder("Filter").fill("number parameter")
        #     page.get_by_placeholder("Filter").press("Enter")

        # # connect the parameter
        # page.get_by_test_id("nodeTreeItem").filter(has_text="jsonifier").all()[
        #     1
        # ].click()
        # page.get_by_test_id("connect_input_btn_number_1").click()
        # page.get_by_text("set existing parameter").nth(1).click()
        # page.wait_for_timeout(1000)
        # page.get_by_text("Number Parameter").click()
        # page.wait_for_timeout(5000)
        page.get_by_test_id("connect_input_btn_number_1").click()
        page.get_by_text("new parameter").click()

        # rename the project to identify it
        page.get_by_test_id("nodesTree").first.click()
        page.get_by_test_id("nodesTree").first.press("F2")
        page.get_by_test_id("nodesTree").first.fill("RSM study")
    # 2. convert it to a function
    # 3. start a RSM with that function

    # with log_context(
    #     logging.INFO,
    #     f"Waiting for {service_key} to be responsive (waiting for {_DEFAULT_RESPONSE_TO_WAIT_FOR})",
    # ):
    #     project_data = create_project_from_service_dashboard(
    #         ServiceType.DYNAMIC, service_key, None, service_version
    #     )
    #     assert "workbench" in project_data, "Expected workbench to be in project data!"
    #     assert isinstance(project_data["workbench"], dict), (
    #         "Expected workbench to be a dict!"
    #     )
    #     node_ids: list[str] = list(project_data["workbench"])
    #     assert len(node_ids) == 1, "Expected 1 node in the workbench!"

    #     wait_for_service_running(
    #         page=page,
    #         node_id=node_ids[0],
    #         websocket=log_in_and_out,
    #         timeout=_WAITING_FOR_SERVICE_TO_START,
    #         press_start_button=False,
    #         product_url=product_url,
    #         is_service_legacy=is_service_legacy,
    #     )

    # service_iframe = page.frame_locator("iframe")
    # with log_context(logging.INFO, "Waiting for the RSM to be ready..."):
    #     service_iframe.get_by_role("grid").wait_for(
    #         state="visible", timeout=_WAITING_FOR_SERVICE_TO_APPEAR
    #     )

    # # select the function
    # service_iframe.get_by_role("gridcell", name=_FUNCTION_NAME).click()

    # # Find the first input field (textbox) in the iframe
    # min_input_field = service_iframe.get_by_role("textbox").nth(0)
    # min_input_field.fill("1")
    # max_input_field = service_iframe.get_by_role("textbox").nth(1)
    # max_input_field.fill("10")

    # # click on next
    # service_iframe.get_by_role("button", name="Next").click()

    # # then we wait a long time
    # page.wait_for_timeout(1 * MINUTE)
