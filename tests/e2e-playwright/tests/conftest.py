# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=no-name-in-module

import logging
import os
import random
import re
from collections.abc import Callable, Iterator

import pytest
from faker import Faker
from playwright.sync_api import APIRequestContext, BrowserContext, Page, WebSocket
from pydantic import AnyUrl, TypeAdapter
from pytest_simcore.logging_utils import log_context
from pytest_simcore.playwright_utils import (
    AutoRegisteredUser,
    SocketIOEvent,
    SocketIOProjectStateUpdatedWaiter,
    decode_socketio_42_message,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup(
        "oSparc e2e options", description="oSPARC-e2e specific parameters"
    )
    group.addoption(
        "--product-url",
        action="store",
        type=AnyUrl,
        default=None,
        help="URL pointing to the deployment to be tested",
    )
    group.addoption(
        "--autoregister",
        action="store_true",
        default=False,
        help="User name for logging into the deployment",
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
        action="store_true",
        default=False,
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


@pytest.fixture(autouse=True)
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
def user_name(request: pytest.FixtureRequest, auto_register: bool, faker: Faker) -> str:
    if auto_register:
        faker.seed_instance(random.randint(0, 10000000000))  # noqa: S311
        return f"pytest_autoregistered_{faker.email()}"
    if osparc_user_name := request.config.getoption("--user-name"):
        assert isinstance(osparc_user_name, str)
        return osparc_user_name
    return os.environ["USER_NAME"]


@pytest.fixture
def user_password(
    request: pytest.FixtureRequest, auto_register: bool, faker: Faker
) -> str:
    if auto_register:
        return faker.password(length=12)
    if osparc_password := request.config.getoption("--password"):
        assert isinstance(osparc_password, str)
        return osparc_password
    return os.environ["USER_PASSWORD"]


@pytest.fixture
def product_billable(request: pytest.FixtureRequest) -> bool:
    billable = request.config.getoption("--product-billable")
    return TypeAdapter(bool).validate_python(billable)


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
def auto_register(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--autoregister"))


@pytest.fixture
def register(
    page: Page,
    product_url: AnyUrl,
    user_name: str,
    user_password: str,
) -> Callable[[], AutoRegisteredUser]:
    def _do() -> AutoRegisteredUser:
        with log_context(
            logging.INFO,
            f"------> Registering in {product_url=} using {user_name=}/{user_password=}",
        ):
            response = page.goto(f"{product_url}")
            assert response
            assert response.ok, response.body()
            page.get_by_test_id("loginCreateAccountBtn").click()
            user_email_box = page.get_by_test_id("registrationEmailFld")
            user_email_box.click()
            user_email_box.fill(user_name)
            for pass_id in ["registrationPass1Fld", "registrationPass2Fld"]:
                user_password_box = page.get_by_test_id(pass_id)
                user_password_box.click()
                user_password_box.fill(user_password)
            with page.expect_response(re.compile(r"/auth/register")) as response_info:
                page.get_by_test_id("registrationSubmitBtn").click()
            assert response_info.value.ok, response_info.value.json()
            return AutoRegisteredUser(user_email=user_name, password=user_password)

    return _do


@pytest.fixture
def log_in_and_out(
    page: Page,
    product_url: AnyUrl,
    user_name: str,
    user_password: str,
    auto_register: bool,
    register: Callable[[], AutoRegisteredUser],
) -> Iterator[WebSocket]:
    with log_context(
        logging.INFO,
        (
            f"------> Opening {product_url=} using {user_name=}/{user_password=}/{auto_register=}",
            f"-----> Opened {product_url=} successfully",
        ),
    ):
        response = page.goto(f"{product_url}")
        assert response
        assert response.ok, response.body()

    # In case the accept cookies or new release window shows up, we accept
    page.wait_for_timeout(2000)
    acceptCookiesBtnLocator = page.get_by_test_id("acceptCookiesBtn")
    if acceptCookiesBtnLocator.is_visible():
        acceptCookiesBtnLocator.click()
        page.wait_for_timeout(1000)
        newReleaseCloseBtnLocator = page.get_by_test_id("newReleaseCloseBtn")
        if newReleaseCloseBtnLocator.is_visible():
            newReleaseCloseBtnLocator.click()

    with page.expect_websocket() as ws_info:
        if auto_register:
            register()
        else:
            with log_context(
                logging.INFO,
                f"------> Logging in {product_url=} using {user_name=}/{user_password=}",
            ):
                _user_email_box = page.get_by_test_id("loginUserEmailFld")
                _user_email_box.click()
                _user_email_box.fill(user_name)
                _user_password_box = page.get_by_test_id("loginPasswordFld")
                _user_password_box.click()
                _user_password_box.fill(user_password)
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

    with log_context(
        logging.INFO,
        (
            "<------ Logging out of %s",
            "<------ Logged out of %s",
        ),
        f"{product_url=} using {user_name=}/{user_password=}",
    ):
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
        page.wait_for_timeout(500)


@pytest.fixture
def create_new_project_and_delete(
    page: Page,
    log_in_and_out: WebSocket,
    product_billable: bool,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
) -> Iterator[Callable[[bool], None]]:
    """The first available service currently displayed in the dashboard will be opened"""
    created_project_uuids = []

    def _do(auto_delete: bool) -> None:

        with log_context(
            logging.INFO,
            f"------> Opening project in {product_url=} as {product_billable=}",
        ) as ctx:
            waiter = SocketIOProjectStateUpdatedWaiter(expected_states=("NOT_STARTED",))
            with log_in_and_out.expect_event(
                "framereceived", waiter
            ), page.expect_response(
                re.compile(r"/projects/[^:]+:open")
            ) as response_info:
                # Project detail view pop-ups shows
                page.get_by_test_id("openResource").click()
                if product_billable:
                    # Open project with default resources
                    page.get_by_test_id("openWithResources").click()
            project_data = response_info.value.json()
            assert project_data
            project_uuid = project_data["data"]["uuid"]

            ctx.messages.done = (
                f"------> Opened project with {project_uuid=} in {product_url=} as {product_billable=}",
            )
            if auto_delete:
                created_project_uuids.append(project_uuid)

    yield _do

    for project_uuid in created_project_uuids:
        with log_context(
            logging.INFO,
            (
                "<------ Deleting project with %s",
                "<------ Deleted project with %s",
            ),
            f"{project_uuid=} in {product_url=} as {product_billable=}",
        ):

            api_request_context.delete(f"{product_url}v0/projects/{project_uuid}")


@pytest.fixture
def start_and_stop_pipeline(
    product_url: AnyUrl,
    page: Page,
    log_in_and_out: WebSocket,
    api_request_context: APIRequestContext,
) -> Iterator[Callable[[], SocketIOEvent]]:
    started_pipeline_ids = []

    def _do() -> SocketIOEvent:
        with log_context(
            logging.INFO,
            f"------> Starting computation in {product_url=}...",
        ) as ctx:
            waiter = SocketIOProjectStateUpdatedWaiter(
                expected_states=(
                    "PUBLISHED",
                    "PENDING",
                    "WAITING_FOR_CLUSTER",
                    "WAITING_FOR_RESOURCES",
                    "STARTED",
                )
            )
            with page.expect_request(
                lambda request: re.search(r"/computations", request.url)
                and request.method.upper() == "POST"  # type: ignore
            ) as request_info, log_in_and_out.expect_event(
                "framereceived", waiter
            ) as event:
                page.get_by_test_id("runStudyBtn").click()
            response = request_info.value.response()
            assert response
            assert response.ok, f"{response.json()}"
            response_body = response.json()
            assert "data" in response_body
            assert "pipeline_id" in response_body["data"]

            pipeline_id = response_body["data"]["pipeline_id"]
            started_pipeline_ids.append(pipeline_id)

            ctx.messages.done = (
                f"------> Started computation with {pipeline_id=} in {product_url=}..."
            )

            return decode_socketio_42_message(event.value)

    yield _do

    # ensure all the pipelines are stopped properly
    for pipeline_id in started_pipeline_ids:
        with log_context(
            logging.INFO,
            (
                "<------ Stopping computation with %s",
                "<------ Stopped computation with %s",
            ),
            f"{pipeline_id=} in {product_url=}...",
        ):
            api_request_context.post(f"{product_url}v0/computations/{pipeline_id}:stop")
