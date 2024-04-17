# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import re
from typing import Final

from playwright.sync_api import Page
from pytest_simcore.playwright_utils import on_web_socket_default_handler

projects_uuid_pattern: Final[re.Pattern] = re.compile(
    r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def test_tip(
    page: Page,
):
    # connect and listen to websocket
    page.on("websocket", on_web_socket_default_handler)

    # open services tab and filter for the service
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
