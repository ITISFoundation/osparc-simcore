# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import os
import re
import pytest
from playwright.sync_api import BrowserContext, Page, APIRequestContext
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

PRODUCT_URL = os.environ["PRODUCT_URL"]
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
def api_request_context(context: BrowserContext):

    yield context.request


@pytest.fixture
def log_in_and_out(osparc_test_id_attribute: None, api_request_context: APIRequestContext, page: Page):
    print("Before test: Logging in starts")
    page.goto(PRODUCT_URL)

    # In case the accept cookies or new release window shows up, we accept
    page.wait_for_timeout(2000)
    acceptCookiesBtnLocator = page.get_by_test_id("acceptCookiesBtn")
    if acceptCookiesBtnLocator.is_visible():
        acceptCookiesBtnLocator.click()
        page.wait_for_timeout(1000)
        newReleaseCloseBtnLocator = page.get_by_test_id("newReleaseCloseBtn")
        if newReleaseCloseBtnLocator.is_visible():
            newReleaseCloseBtnLocator.click()

    _user_email_box = page.get_by_test_id("loginUserEmailFld")
    _user_email_box.click()
    _user_email_box.fill(USER_NAME)
    _user_password_box = page.get_by_test_id("loginPasswordFld")
    _user_password_box.click()
    _user_password_box.fill(USER_PASSWORD)
    page.get_by_test_id("loginSubmitBtn").click()

    yield

    print("After test cleaning: Logging out starts")
    api_request_context.post(f"{PRODUCT_URL}v0/auth/logout")

@pytest.mark.testit
def test_billable_sim4life(page: Page, log_in_and_out: None, api_request_context: APIRequestContext):
    # connect and listen to websocket
    page.on("websocket", on_web_socket)

    # Welcome to Sim4Life
    page.wait_for_timeout(2000)
    welcomeToSim4LifeLocator = page.get_by_text("Welcome to Sim4Life")
    if welcomeToSim4LifeLocator.is_visible():
        page.get_by_text("").nth(1).click()  # There is missing osparc-test-id for this button

    # open services tab and filter for sim4life service
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill(SERVICE_KEY)
    _textbox.press("Enter")
    page.get_by_test_id(SERVICE_TEST_ID).click()

    with page.expect_response(re.compile(r'/projects/')) as response_info:
        # Project detail view pop-ups shows
        page.get_by_test_id("openResource").click()
        # Open project with default resources
        page.get_by_test_id("openWithResources").click()
        page.wait_for_timeout(1000)

    # Get project uuid, will be used to delete this project in the end
    uuid_pattern = re.compile(r'/projects/([0-9a-fA-F-]+)')
    match = uuid_pattern.search(response_info.value.url)
    extracted_uuid = match.group(1)

    # Wait until grid is shown and click on the similation button
    page.frame_locator(".qx-main-dark").get_by_role("img", name="Remote render").click(
        button="right", timeout=600000
    )
    page.frame_locator(".qx-main-dark").get_by_text("Simulation").click()
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
            resp = api_request_context.delete(f"{PRODUCT_URL}v0/projects/{extracted_uuid}")
            assert resp.status == 204
