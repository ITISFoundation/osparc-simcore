# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import re
from http import HTTPStatus

from playwright.sync_api import APIRequestContext, Page
from pydantic import AnyUrl
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


def on_web_socket(ws) -> None:
    print(f"WebSocket opened: {ws.url}")
    ws.on("framesent", lambda payload: print(payload))
    ws.on("framereceived", lambda payload: print(payload))
    ws.on("close", lambda payload: print("WebSocket closed"))


def test_sim4life(
    page: Page,
    log_in_and_out: None,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    product_billable: bool,
    service_key: str,
    service_test_id: str,
):
    # connect and listen to websocket
    page.on("websocket", on_web_socket)

    # open services tab and filter for sim4life service
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill(service_key)
    _textbox.press("Enter")
    page.get_by_test_id(service_test_id).click()

    with page.expect_response(re.compile(r"/projects/")) as response_info:
        # Project detail view pop-ups shows
        page.get_by_test_id("openResource").click()
        if product_billable:
            # Open project with default resources
            page.get_by_test_id("openWithResources").click()
        page.wait_for_timeout(1000)

    # Get project uuid, will be used to delete this project in the end
    uuid_pattern = re.compile(r"/projects/([0-9a-fA-F-]+)")
    match = uuid_pattern.search(response_info.value.url)
    assert match
    extracted_uuid = match.group(1)

    # Wait until grid is shown
    page.frame_locator(".qx-main-dark").get_by_role("img", name="Remote render").click(
        button="right", timeout=600000
    )
    page.wait_for_timeout(1000)

    # Going back to dashboard
    page.get_by_test_id("dashboardBtn").click()
    page.get_by_test_id("confirmDashboardBtn").click()
    page.wait_for_timeout(1000)

    # Going back to projecs/studies view (In Sim4life projects:=studies)
    page.get_by_test_id("studiesTabBtn").click()
    page.wait_for_timeout(1000)

    # TODO: this is not the way, here we do not test the UI

    # The project is closing, wait until it is closed and delete it (currently waits max=5 minutes)
    for attempt in Retrying(
        wait=wait_fixed(5),
        stop=stop_after_attempt(60),  # 5*60= 300 seconds
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            resp = api_request_context.delete(
                f"{product_url}v0/projects/{extracted_uuid}"
            )
            assert resp.status == HTTPStatus.NO_CONTENT
