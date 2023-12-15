# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements

import os
import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import APIRequestContext, BrowserContext, Page, WebSocket
from pydantic import AnyUrl, TypeAdapter


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="contains all e2e specific parameters"
    )
    group.addoption(
        "--product-url",
        action="store",
        type=AnyUrl,
        default=None,
        help="URL pointing to the deployment to be tested",
    )
    group.addoption(
        "--user-name",
        action="store",
        type=str,
        default=None,
        help="User name for logging into the deployment",
    )
    group.addoption(
        "--password",
        action="store",
        type=str,
        default=None,
        help="Password for logging into the deployment",
    )
    group.addoption(
        "--product-billable",
        action="store",
        type=str,
        default=None,
        help="Whether product is billable or not",
    )
    group.addoption(
        "--service-test-id",
        action="store",
        type=str,
        default=None,
        help="Service test ID",
    )
    group.addoption(
        "--service-key",
        action="store",
        type=str,
        default=None,
        help="Service Key",
    )


@pytest.fixture
def osparc_test_id_attribute(playwright):
    # Set a custom test id attribute
    playwright.selectors.set_test_id_attribute("osparc-test-id")


@pytest.fixture
def api_request_context(context: BrowserContext):
    return context.request


@pytest.fixture
def product_url(request: pytest.FixtureRequest) -> AnyUrl:
    if passed_product_url := request.config.getoption("--product-url"):
        return TypeAdapter(AnyUrl).validate_python(passed_product_url)
    return TypeAdapter(AnyUrl).validate_python(os.environ["PRODUCT_URL"])


@pytest.fixture
def user_name(request: pytest.FixtureRequest) -> str:
    if osparc_user_name := request.config.getoption("--user-name"):
        assert isinstance(osparc_user_name, str)
        return osparc_user_name
    return os.environ["USER_NAME"]


@pytest.fixture
def user_password(request: pytest.FixtureRequest) -> str:
    if osparc_password := request.config.getoption("--password"):
        assert isinstance(osparc_password, str)
        return osparc_password
    return os.environ["USER_PASSWORD"]


@pytest.fixture
def product_billable(request: pytest.FixtureRequest) -> bool:
    if billable := request.config.getoption("--product-billable"):
        assert isinstance(billable, str)
        return TypeAdapter(bool).validate_python(billable)
    return TypeAdapter(bool).validate_python(os.environ["PRODUCT_BILLABLE"])


@pytest.fixture
def service_test_id(request: pytest.FixtureRequest) -> str:
    if test_id := request.config.getoption("--service-test-id"):
        assert isinstance(test_id, str)
        return test_id
    return os.environ["SERVICE_TEST_ID"]


@pytest.fixture
def service_key(request: pytest.FixtureRequest) -> str:
    if key := request.config.getoption("--service-key"):
        assert isinstance(key, str)
        return key
    return os.environ["SERVICE_KEY"]


@pytest.fixture
def log_in_and_out(
    osparc_test_id_attribute: None,
    api_request_context: APIRequestContext,
    page: Page,
    product_url: AnyUrl,
    user_name: str,
    user_password: str,
) -> Iterator[WebSocket]:
    print(f"------> Logging in {product_url=} using {user_name=}/{user_password=}")
    page.goto(f"{product_url}")

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
    # check the websocket got created
    with page.expect_websocket() as ws_info:
        with page.expect_response(re.compile(r"/login")) as response_info:
            page.get_by_test_id("loginSubmitBtn").click()
        assert response_info.value.ok, f"{response_info.value.json()}"
    ws = ws_info.value
    assert not ws.is_closed()

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

    yield ws

    print(f"<------ Logging out of {product_url=} using {user_name=}/{user_password=}")
    # click anywher to remove modal windows
    page.click(
        "body",
        position={"x": 0, "y": 0},
    )
    page.get_by_test_id("userMenuBtn").click()
    with page.expect_response(re.compile(r"/auth/logout")) as response_info:
        page.get_by_test_id("userMenuLogoutBtn").click()
    assert response_info.value.ok, f"{response_info.value.json()}"
    # so we see the logout page
    page.wait_for_timeout(2000)
    print(f"<------ Logged out of {product_url=} using {user_name=}/{user_password=}")
