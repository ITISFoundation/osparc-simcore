# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import os
import re
import pytest
from http import HTTPStatus
from playwright.sync_api import  Page, APIRequestContext
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

PRODUCT_URL = os.environ["PRODUCT_URL"]
PRODUCT_BILLABLE = os.environ["PRODUCT_BILLABLE"]
USER_NAME = os.environ["USER_NAME"]
USER_PASSWORD = os.environ["USER_PASSWORD"]
SERVICE_TEST_ID = os.environ["SERVICE_TEST_ID"]
SERVICE_KEY = os.environ["SERVICE_KEY"]


def on_web_socket(ws):
    print(f"WebSocket opened: {ws.url}")
    ws.on("framesent", lambda payload: print(payload))
    ws.on("framereceived", lambda payload: print(payload))
    ws.on("close", lambda payload: print("WebSocket closed"))


@pytest.fixture
def product_and_user() -> tuple:
    product_url = PRODUCT_URL
    user_name = USER_NAME
    user_password = USER_PASSWORD
    return (product_url, user_name, user_password)


def test_sim4life(page: Page, log_in_and_out: None, api_request_context: APIRequestContext):
    # connect and listen to websocket
    page.on("websocket", on_web_socket)

<<<<<<< HEAD
=======
    # Welcome to Sim4Life
    page.wait_for_timeout(5000)
    welcomeToSim4LifeLocator = page.get_by_text("Welcome to Sim4Life")
    if welcomeToSim4LifeLocator.is_visible():
        page.get_by_text("").nth(1).click()  # There is missing osparc-test-id for this button
    # Quick start window
    quickStartWindowCloseBtnLocator = page.get_by_test_id("quickStartWindowCloseBtn")
    if quickStartWindowCloseBtnLocator.is_visible():
        quickStartWindowCloseBtnLocator.click()

>>>>>>> 8d534da9a561a346c9c9ff4d9b8f9f7b75e09ca9
    # open services tab and filter for sim4life service
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill(SERVICE_KEY)
    _textbox.press("Enter")
    page.get_by_test_id(SERVICE_TEST_ID).click()

    with page.expect_response(re.compile(r'/projects/')) as response_info:
        # Project detail view pop-ups shows
        page.get_by_test_id("openResource").click()
        if bool(int(PRODUCT_BILLABLE)):
            # Open project with default resources
            page.get_by_test_id("openWithResources").click()
        page.wait_for_timeout(1000)

    # Get project uuid, will be used to delete this project in the end
    uuid_pattern = re.compile(r'/projects/([0-9a-fA-F-]+)')
    match = uuid_pattern.search(response_info.value.url)
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

    # The project is closing, wait until it is closed and delete it (currently waits max=5 minutes)
    for attempt in Retrying(
        wait=wait_fixed(5),
        stop=stop_after_attempt(60),  # 5*60= 300 seconds
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(attempt)
            resp = api_request_context.delete(f"{PRODUCT_URL}v0/projects/{extracted_uuid}")
            assert resp.status == HTTPStatus.NO_CONTENT
