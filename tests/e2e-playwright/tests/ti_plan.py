# pytest -s tests/ti_plan.py --color=yes --product-url=https://tip-master.speag.com/ --user-name=[user_name] --password=[password] --tracing on --junitxml=report.xml --browser chromium


# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import re
import time
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

    # Electrode Selector
    start = time.time()
    page.frame_locator(".qx-main-dark").get_by_test_id(
        "TargetStructure_Selector"
    ).select_option(label="TargetStructure_Target_(Targets_combined) Hypothalamus")
    # at this point the Electrode Selector is ready
    end = time.time()
    print("Electrode Selector ready in ", end - start, "s")
    page.get_by_test_id(
        "TargetStructure_Target_(Targets_combined) Hypothalamus"
    ).click()
    electrode_selections = [
        ["E1+", "FT9"],
        ["E1-", "FT7"],
        ["E2+", "T9"],
        ["E2-", "T7"],
    ]
    for selection in electrode_selections:
        page.get_by_test_id("ElectrodeGroup_" + selection[0] + "_Start").click()
        page.get_by_test_id("Electrode_" + selection[1]).click()
    page.get_by_test_id("FinishSetUp").click()
