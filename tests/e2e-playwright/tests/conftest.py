# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import pytest
from playwright.sync_api import BrowserContext, Page, APIRequestContext
from typing import Iterator


@pytest.fixture
def osparc_test_id_attribute(playwright):
    # Set a custom test id attribute
    playwright.selectors.set_test_id_attribute("osparc-test-id")


@pytest.fixture
def api_request_context(context: BrowserContext):

    yield context.request


@pytest.fixture
def log_in_and_out(osparc_test_id_attribute: None, api_request_context: APIRequestContext, page: Page, product_and_user: tuple) -> Iterator[None]:
    print("Before test: Logging in starts")
    page.goto(product_and_user[0])

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
    _user_email_box.fill(product_and_user[1])
    _user_password_box = page.get_by_test_id("loginPasswordFld")
    _user_password_box.click()
    _user_password_box.fill(product_and_user[2])
    page.get_by_test_id("loginSubmitBtn").click()

    # Welcome to Sim4Life
    page.wait_for_timeout(5000)
    welcomeToSim4LifeLocator = page.get_by_text("Welcome to Sim4Life")
    if welcomeToSim4LifeLocator.is_visible():
        page.get_by_text("").nth(1).click()  # There is missing osparc-test-id for this button
    # Quick start window
    quickStartWindowCloseBtnLocator = page.get_by_test_id("quickStartWindowCloseBtn")
    if quickStartWindowCloseBtnLocator.is_visible():
        quickStartWindowCloseBtnLocator.click()

    yield

    print("After test cleaning: Logging out starts")
    api_request_context.post(f"{product_and_user[0]}v0/auth/logout")
