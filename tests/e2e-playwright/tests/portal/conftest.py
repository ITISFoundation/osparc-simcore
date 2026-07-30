# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Portal e2e-playwright suite.

Ports the legacy Puppeteer scripts in tests/e2e/portal/*.js, tests/e2e/portal-files/VTK_file.js
and tests/e2e/publications/*.js: opens a public/portal study without logging in (see
`open_study_link` below) and interacts with the service(s) it contains.

Shared fixtures such as `api_request_context` are defined in the parent conftest.py. Each test
hardcodes its own `is_service_legacy`-equivalent value (matching the legacy JS
`waitForServices(..., waitForConnected)` argument for that specific service) since it's a fixed
property of the service, not something the user should have to configure per run.
"""

import datetime
import logging
import re
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import pytest
from playwright.sync_api import Page
from pydantic import AnyUrl, TypeAdapter
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import MINUTE, RobustWebSocket

_OPENING_TUTORIAL_MAX_WAIT_TIME: Final[int] = 3 * MINUTE


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("oSparc e2e options", description="oSPARC-e2e specific parameters")
    group.addoption(
        "--anonymous-study-url",
        action="store",
        type=str,
        default=None,
        help="Full URL pointing to a public/portal study that can be opened without logging in "
        "(equivalent to url_prefix+template_uuid in the legacy tests/e2e/portal scripts)",
    )
    group.addoption(
        "--anonymous-open-timeout",
        action="store",
        type=int,
        default=_OPENING_TUTORIAL_MAX_WAIT_TIME,
        help="Timeout in milliseconds to wait for the anonymous study to open",
    )
    group.addoption(
        "--service-start-timeout",
        action="store",
        type=int,
        default=1 * MINUTE,
        help="timeout in milliseconds waiting for an anonymously-opened study's service(s) to "
        "become ready (equivalent to the legacy start_timeout CLI argument)",
    )
    group.addoption(
        "--run-pipeline-timeout",
        action="store",
        type=int,
        default=3 * MINUTE,
        help="timeout in milliseconds waiting for a computational pipeline run to complete "
        "(equivalent to the legacy start_timeout CLI argument)",
    )
    group.addoption(
        "--viewer-url-prefix",
        action="store",
        type=str,
        default=None,
        help="Base URL used to resolve the public viewer via /v0/viewers/default "
        "(used by test_vtk_file.py; equivalent to the legacy url_prefix CLI argument)",
    )
    group.addoption(
        "--download-link",
        action="store",
        type=str,
        default=None,
        help="URL of the file to open in the viewer (used by test_vtk_file.py)",
    )
    group.addoption(
        "--file-size",
        action="store",
        type=str,
        default=None,
        help="Size (in bytes) of the file behind --download-link (used by test_vtk_file.py)",
    )


@pytest.fixture(scope="session")
def anonymous_study_url(request: pytest.FixtureRequest) -> str:
    """Full URL of a public/portal study that can be opened without logging in."""
    url = request.config.getoption("--anonymous-study-url")
    assert url, "missing --anonymous-study-url option"
    assert isinstance(url, str)
    return url


@pytest.fixture(scope="session")
def anonymous_open_timeout(request: pytest.FixtureRequest) -> int:
    timeout = request.config.getoption("--anonymous-open-timeout")
    assert isinstance(timeout, int)
    return timeout


@pytest.fixture(scope="session")
def service_start_timeout(request: pytest.FixtureRequest) -> int:
    timeout = request.config.getoption("--service-start-timeout")
    assert isinstance(timeout, int)
    return timeout


@pytest.fixture(scope="session")
def run_pipeline_timeout(request: pytest.FixtureRequest) -> int:
    timeout = request.config.getoption("--run-pipeline-timeout")
    assert isinstance(timeout, int)
    return timeout


@dataclass(slots=True, kw_only=True)
class OpenedAnonymousStudy:
    """Result of opening a public/portal study link without logging in."""

    project_data: dict[str, Any]
    websocket: RobustWebSocket
    product_url: AnyUrl


@pytest.fixture
def open_study_link(page: Page, anonymous_open_timeout: int) -> Callable[..., OpenedAnonymousStudy]:
    """Opens a public/portal study by URL without any login/registration.

    This is the Playwright equivalent of the legacy Puppeteer
    `TutorialBase.openStudyLink()` used by tests/e2e/portal, tests/e2e/portal-files
    and tests/e2e/publications (all ported into tests/portal).
    """

    def _(url: str, *, timeout: int | None = None) -> OpenedAnonymousStudy:
        timeout = timeout if timeout is not None else anonymous_open_timeout
        with (
            log_context(
                logging.INFO,
                f"Opening anonymous study link {url=} (timeout {datetime.timedelta(milliseconds=timeout)})",
            ),
            page.expect_websocket(timeout=timeout) as ws_info,
            page.expect_response(re.compile(r"/projects/[^:]+:open"), timeout=timeout) as response_info,
        ):
            response = page.goto(url)
            assert response
            assert response.ok, response.body()

        # In case the accept cookies or new release window shows up, we accept
        page.wait_for_timeout(2000)
        accept_cookies_btn_locator = page.get_by_test_id("acceptCookiesBtn")
        if accept_cookies_btn_locator.is_visible():
            accept_cookies_btn_locator.click()
            page.wait_for_timeout(1000)
            new_release_close_btn_locator = page.get_by_test_id("newReleaseCloseBtn")
            if new_release_close_btn_locator.is_visible():
                new_release_close_btn_locator.click()

        assert response_info.value.ok, f"{response_info.value.json()}"
        project_data = response_info.value.json()["data"]

        assert not ws_info.value.is_closed()
        websocket = RobustWebSocket(page, ws_info.value)

        # NOTE: the anonymous_study_url might redirect to a different host (e.g. a vanity
        # domain), so the product host is derived from the page's final URL
        parsed_url = urllib.parse.urlparse(page.url)
        product_url = TypeAdapter(AnyUrl).validate_python(f"{parsed_url.scheme}://{parsed_url.netloc}/")

        return OpenedAnonymousStudy(project_data=project_data, websocket=websocket, product_url=product_url)

    return _


@pytest.fixture
def viewer_url_prefix(request: pytest.FixtureRequest) -> str:
    url_prefix = request.config.getoption("--viewer-url-prefix")
    assert url_prefix, "missing --viewer-url-prefix option"
    assert isinstance(url_prefix, str)
    return url_prefix


@pytest.fixture
def download_link(request: pytest.FixtureRequest) -> str:
    link = request.config.getoption("--download-link")
    assert link, "missing --download-link option"
    assert isinstance(link, str)
    return link


@pytest.fixture
def file_size(request: pytest.FixtureRequest) -> str:
    size = request.config.getoption("--file-size")
    assert size, "missing --file-size option"
    assert isinstance(size, str)
    return size
