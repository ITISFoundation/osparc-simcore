import os

import pytest
from playwright.sync_api import BrowserContext, Page

PRODUCT_URL = os.getenv("PRODUCT_URL")
USER_NAME = os.getenv("USER_NAME")
USER_PASSWORD = os.getenv("USER_PASSWORD")
SERVICE_TEST_ID = os.getenv("SERVICE_TEST_ID")
SERVICE_KEY = os.getenv("SERVICE_KEY")


def on_web_socket(ws):
    print(f"WebSocket opened: {ws.url}")
    ws.on("framesent", lambda payload: print(payload))
    ws.on("framereceived", lambda payload: print(payload))
    ws.on("close", lambda payload: print("WebSocket closed"))


@pytest.fixture
def log_in_and_out(osparc_test_id_attribute, context: BrowserContext, page: Page):
    print("Before test: Logging in starts")
    page.goto(PRODUCT_URL)

    _user_email_box = page.get_by_test_id("loginUserEmailFld")
    _user_email_box.click()
    _user_email_box.fill(USER_NAME)
    _user_password_box = page.get_by_test_id("loginPasswordFld")
    _user_password_box.click()
    _user_password_box.fill(USER_PASSWORD)
    page.get_by_test_id("loginSubmitBtn").click()

    yield

    print("After test cleaning: Logging out starts")
    api_request_context = context.request
    api_request_context.post(f"{PRODUCT_URL}v0/auth/logout")


def test_billable_sim4life(page: Page, log_in_and_out) -> None:
    # connect and listen to websocket
    page.on("websocket", on_web_socket)

    # open services tab and filter for sim4life service
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill(SERVICE_KEY)
    _textbox.press("Enter")
    page.get_by_test_id(SERVICE_TEST_ID).click()

    # Project detail view pop-ups shows
    page.get_by_test_id("openResource").click()
    # Open project with default resources
    page.get_by_test_id("openWithResources").click()
    page.wait_for_timeout(5000)

    # Wait until grid is shown and click on the similation button
    page.frame_locator(".qx-main-dark").get_by_role("img", name="Remote render").click(
        button="right", timeout=600000
    )
    page.frame_locator(".qx-main-dark").get_by_text("Simulation").click()
    page.wait_for_timeout(5000)

    # Going back to dashboard
    page.get_by_test_id("dashboardBtn").click()
    page.get_by_test_id("confirmDashboardBtn").click()
    page.wait_for_timeout(5000)

    # Going back to projecs/studies view (In Sim4life projects:=studies)
    page.get_by_test_id("studiesTabBtn").click()
    page.wait_for_timeout(5000)
