# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime
import json
import logging
import os
import random
import re
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any, Final

import arrow
import pytest
from faker import Faker
from playwright.sync_api import APIRequestContext, BrowserContext, Page, WebSocket
from playwright.sync_api._generated import Playwright
from pydantic import AnyUrl, TypeAdapter
from pytest import Item
from pytest_simcore.helpers.logging import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    AutoRegisteredUser,
    RunningState,
    ServiceType,
    SocketIOEvent,
    SocketIOProjectClosedWaiter,
    SocketIOProjectStateUpdatedWaiter,
    decode_socketio_42_message,
)

_PROJECT_CLOSING_TIMEOUT: Final[int] = 10 * MINUTE


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
        "--autoscaled",
        action="store_true",
        default=False,
        help="Whether test runs against autoscaled  deployment or not",
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
    group.addoption(
        "--user-agent",
        action="store",
        type=str,
        default="e2e-playwright",
        help="defines a specific user agent osparc header",
    )


# Dictionary to store start times of tests
_test_start_times = {}


def pytest_runtest_setup(item):
    """
    Hook to capture the start time of each test.
    """
    _test_start_times[item.name] = arrow.now().datetime


_FORMAT: Final = "%Y-%m-%dT%H:%M:%S.%fZ"


def _construct_graylog_url(
    product_url: str | None, start_time: datetime.datetime, end_time: datetime.datetime
) -> str:
    # Deduce monitoring url
    if product_url:
        scheme, tail = product_url.split("://", 1)
    else:
        scheme, tail = "https", "<UNDEFINED>"
    monitoring_url = f"{scheme}://monitoring.{tail}"

    # build graylog URL
    query = f"from={start_time.strftime(_FORMAT)}&to={end_time.strftime(_FORMAT)}"
    return f"{monitoring_url}/graylog/search?{query}"


def pytest_runtest_makereport(item: Item, call):
    """
    Hook to add extra information when a test fails.
    """

    # Check if the test failed
    if call.when == "call" and call.excinfo is not None:
        test_name = item.name
        test_location = item.location
        product_url = f"{item.config.getoption('--product-url', default=None)}"

        diagnostics = {
            "test_name": test_name,
            "test_location": test_location,
            "product_url": product_url,
        }

        # Get the start and end times of the test
        start_time = _test_start_times.get(test_name)
        end_time = arrow.now().datetime

        if start_time:
            diagnostics["graylog_url"] = _construct_graylog_url(
                product_url, start_time, end_time
            )
            diagnostics["duration"] = str(end_time - start_time)

        # Print the diagnostics report
        print(f"\nDiagnostics repoort for {test_name} ---")
        print(json.dumps(diagnostics, indent=2))
        print("---")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    config.pluginmanager.register(pytest_runtest_setup, "osparc_test_times_plugin")
    config.pluginmanager.register(pytest_runtest_makereport, "osparc_makereport_plugin")


@pytest.fixture(autouse=True)
def osparc_test_id_attribute(playwright: Playwright) -> None:
    # Set a custom test id attribute
    playwright.selectors.set_test_id_attribute("osparc-test-id")


@pytest.fixture
def api_request_context(context: BrowserContext) -> APIRequestContext:
    return context.request


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
def product_billable(request: pytest.FixtureRequest) -> bool:
    billable = request.config.getoption("--product-billable")
    return TypeAdapter(bool).validate_python(billable)


@pytest.fixture(scope="session")
def autoscaled(request: pytest.FixtureRequest) -> bool:
    autoscaled = request.config.getoption("--autoscaled")
    return TypeAdapter(bool).validate_python(autoscaled)


@pytest.fixture(scope="session")
def service_test_id(request: pytest.FixtureRequest) -> str:
    if test_id := request.config.getoption("--service-test-id"):
        assert isinstance(test_id, str)
        return test_id
    return os.environ["SERVICE_TEST_ID"]


@pytest.fixture(scope="session")
def service_key(request: pytest.FixtureRequest) -> str:
    if key := request.config.getoption("--service-key"):
        assert isinstance(key, str)
        return key
    return os.environ["SERVICE_KEY"]


@pytest.fixture(scope="session")
def auto_register(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--autoregister"))


@pytest.fixture(scope="session")
def user_agent(request: pytest.FixtureRequest) -> str:
    return str(request.config.getoption("--user-agent"))


@pytest.fixture(scope="session")
def browser_context_args(
    browser_context_args: dict[str, dict[str, str] | str], user_agent: str
) -> dict[str, dict[str, str] | str]:
    # Override browser context options, see https://playwright.dev/python/docs/test-runners#fixtures
    return {
        **browser_context_args,
        "extra_http_headers": {"X-Simcore-User-Agent": user_agent},
    }


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
        f"Opening {product_url=} using {user_name=}/{user_password=}/{auto_register=}",
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
                f"Logging in {product_url=} using {user_name=}/{user_password=}",
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
        f"Logging out of {product_url=} using {user_name=}/{user_password=}",
    ):
        page.keyboard.press("Escape")
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
) -> Iterator[Callable[[tuple[RunningState], bool], dict[str, Any]]]:
    """The first available service currently displayed in the dashboard will be opened
    NOTE: cannot be used multiple times or going back to dashboard will fail!!
    """
    created_project_uuids = []

    def _(
        expected_states: tuple[RunningState] = (RunningState.NOT_STARTED,),
        press_open: bool = True,
    ) -> dict[str, Any]:
        assert (
            len(created_project_uuids) == 0
        ), "misuse of this fixture! only 1 study can be opened at a time. Otherwise please modify the fixture"
        with log_context(
            logging.INFO,
            f"Opening project in {product_url=} as {product_billable=}",
        ) as ctx:
            waiter = SocketIOProjectStateUpdatedWaiter(expected_states=expected_states)
            with (
                log_in_and_out.expect_event("framereceived", waiter),
                page.expect_response(
                    re.compile(r"/projects/[^:]+:open")
                ) as response_info,
            ):
                # Project detail view pop-ups shows
                if press_open:
                    page.get_by_test_id("openResource").click()
                if product_billable:
                    # Open project with default resources
                    page.get_by_test_id("openWithResources").click()
            project_data = response_info.value.json()
            assert project_data
            project_uuid = project_data["data"]["uuid"]
            ctx.logger.info("%s", f"{project_uuid=}")
            ctx.logger.info(
                "project_workbench=%s",
                f"{json.dumps(project_data['data']['workbench'], indent=2)}",
            )

            created_project_uuids.append(project_uuid)
            return project_data["data"]

    yield _

    # go back to dashboard and wait for project to close
    with ExitStack() as stack:
        for project_uuid in created_project_uuids:
            stack.enter_context(
                log_context(logging.INFO, f"Waiting for closed project {project_uuid=}")
            )
            stack.enter_context(
                log_in_and_out.expect_event(
                    "framereceived",
                    SocketIOProjectClosedWaiter(),
                    timeout=_PROJECT_CLOSING_TIMEOUT,
                )
            )
        if created_project_uuids:
            with log_context(logging.INFO, "Going back to dashboard"):
                page.get_by_test_id("dashboardBtn").click()
                page.get_by_test_id("confirmDashboardBtn").click()
                page.get_by_test_id("studiesTabBtn").click()

    for project_uuid in created_project_uuids:
        with log_context(
            logging.INFO,
            f"Deleting project with {project_uuid=} in {product_url=} as {product_billable=}",
        ):
            response = api_request_context.delete(
                f"{product_url}v0/projects/{project_uuid}"
            )
            assert (
                response.status == 204
            ), f"Unexpected error while deleting project: '{response.json()}'"


# SEE https://github.com/ITISFoundation/osparc-simcore/pull/5618#discussion_r1553943415
_OUTER_CONTEXT_TIMEOUT_MS = 30000  # Default is `30000` (30 seconds)
_INNER_CONTEXT_TIMEOUT_MS = 0.8 * _OUTER_CONTEXT_TIMEOUT_MS


@pytest.fixture
def find_and_start_service_in_dashboard(
    page: Page,
) -> Callable[[ServiceType, str, str | None], None]:
    def _(
        service_type: ServiceType, service_name: str, service_key_prefix: str | None
    ) -> None:
        with log_context(logging.INFO, f"Finding {service_name=} in dashboard"):
            page.get_by_test_id("servicesTabBtn").click()
            _textbox = page.get_by_test_id("searchBarFilter-textField-service")
            _textbox.fill(service_name)
            _textbox.press("Enter")
            test_id = f"studyBrowserListItem_simcore/services/{'dynamic' if service_type is ServiceType.DYNAMIC else 'comp'}"
            if service_key_prefix:
                test_id = f"{test_id}/{service_key_prefix}"
            test_id = f"{test_id}/{service_name}"
            page.get_by_test_id(test_id).click()

    return _


@pytest.fixture
def create_project_from_service_dashboard(
    find_and_start_service_in_dashboard: Callable[[ServiceType, str, str | None], None],
    create_new_project_and_delete: Callable[[tuple[RunningState]], dict[str, Any]],
) -> Callable[[ServiceType, str, str | None], dict[str, Any]]:
    def _(
        service_type: ServiceType, service_name: str, service_key_prefix: str | None
    ) -> dict[str, Any]:
        find_and_start_service_in_dashboard(
            service_type, service_name, service_key_prefix
        )
        expected_states = (RunningState.UNKNOWN,)
        if service_type is ServiceType.COMPUTATIONAL:
            expected_states = (RunningState.NOT_STARTED,)
        return create_new_project_and_delete(expected_states)

    return _


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
                    RunningState.PUBLISHED,
                    RunningState.PENDING,
                    RunningState.WAITING_FOR_CLUSTER,
                    RunningState.WAITING_FOR_RESOURCES,
                    RunningState.STARTED,
                )
            )

            # NOTE: Keep expect_request as an inner context. In case of timeout, we want
            # to know whether the POST was requested or not.
            with (
                log_in_and_out.expect_event(
                    "framereceived",
                    waiter,
                    timeout=_OUTER_CONTEXT_TIMEOUT_MS,
                ) as event,
                page.expect_request(
                    lambda r: re.search(r"/computations", r.url)
                    and r.method.upper() == "POST",  # type: ignore
                    timeout=_INNER_CONTEXT_TIMEOUT_MS,
                ) as request_info,
            ):
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
