# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import os
from collections.abc import Iterator

import pytest
from playwright.sync_api import APIRequestContext, BrowserContext, Page
from pydantic import AnyUrl, TypeAdapter


@pytest.fixture
def osparc_test_id_attribute(playwright):
    # Set a custom test id attribute
    playwright.selectors.set_test_id_attribute("osparc-test-id")


@pytest.fixture
def api_request_context(context: BrowserContext):
    return context.request


@pytest.fixture
def product_url() -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(os.environ["PRODUCT_URL"])


@pytest.fixture
def user_name() -> str:
    return os.environ["USER_NAME"]


@pytest.fixture
def user_password() -> str:
    return os.environ["USER_PASSWORD"]


@pytest.fixture
def product_billable() -> bool:
    return TypeAdapter(bool).validate_python(os.environ["PRODUCT_BILLABLE"])


@pytest.fixture
def service_test_id() -> str:
    return os.environ["SERVICE_TEST_ID"]


@pytest.fixture
def service_key() -> str:
    return os.environ["SERVICE_KEY"]


@pytest.fixture
def log_in_and_out(
    osparc_test_id_attribute: None,
    api_request_context: APIRequestContext,
    page: Page,
    product_url: AnyUrl,
    user_name: str,
    user_password: str,
) -> Iterator[None]:
    print(f"------> Logging in {product_url=} using {user_name=}/{user_password=}")
    page.goto(product_url)

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
    _user_email_box.fill(user_name)
    _user_password_box = page.get_by_test_id("loginPasswordFld")
    _user_password_box.click()
    _user_password_box.fill(user_password)
    page.get_by_test_id("loginSubmitBtn").click()

    # Welcome to Sim4Life
    page.wait_for_timeout(5000)
    welcomeToSim4LifeLocator = page.get_by_text("Welcome to Sim4Life")
    if welcomeToSim4LifeLocator.is_visible():
        page.get_by_text("").nth(
            1
        ).click()  # There is missing osparc-test-id for this button
    # Quick start window
    quickStartWindowCloseBtnLocator = page.get_by_test_id("quickStartWindowCloseBtn")
    if quickStartWindowCloseBtnLocator.is_visible():
        quickStartWindowCloseBtnLocator.click()
    print(
        f"------> Successfully logged in {product_url=} using {user_name=}/{user_password=}"
    )

    yield

    # TODO: this is not the UI way of logging out
    print(f"<------ Logging out of {product_url=} using {user_name=}/{user_password=}")
    api_request_context.post(f"{product_url}v0/auth/logout")
    print(f"<------ Logged out of {product_url=} using {user_name=}/{user_password=}")
