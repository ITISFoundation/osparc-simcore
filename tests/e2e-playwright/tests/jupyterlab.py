# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import re
from http import HTTPStatus
from typing import Final

from playwright.sync_api import APIRequestContext, Page
from pydantic import AnyUrl
from pytest_simcore.logging_utils import test_logger
from pytest_simcore.playwright_utils import on_web_socket_default_handler
from tenacity import Retrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

projects_uuid_pattern: Final[re.Pattern] = re.compile(
    r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def test_jupyterlab(
    page: Page,
    log_in_and_out: None,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    product_billable: bool,
    service_key: str,
    service_test_id: str,
):
    # connect and listen to websocket
    page.on("websocket", on_web_socket_default_handler)

    # open services tab and filter for the service
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill(service_key)
    _textbox.press("Enter")
    page.get_by_test_id(service_test_id).click()

    with page.expect_response(projects_uuid_pattern) as response_info:
        # Project detail view pop-ups shows
        page.get_by_test_id("openResource").click()
        if product_billable:
            # Open project with default resources
            page.get_by_test_id("openWithResources").click()
        page.wait_for_timeout(1000)

    # Get project uuid, will be used to delete this project in the end
    test_logger.info(f"projects uuid endpoint captured: {response_info.value.url}")
    match = projects_uuid_pattern.search(response_info.value.url)
    assert match
    extracted_uuid = match.group(1)

    # Wait until iframe is shown and create new notebook with print statement
    page.frame_locator(".qx-main-dark").get_by_role(
        "button", name="New Launcher"
    ).click(timeout=600000)
    if "jupyter-octave-python-math" in service_key or "jupyter-math" in service_key:
        # Python Math service
        # NOTE MD: as currently jupyter python math UI test is flaky i will comment it out until it is improved
        ...
    elif "jupyter-smash" in service_key:
        # Jupyter smash service
        page.frame_locator(".qx-main-dark").locator(
            ".jp-LauncherCard-icon"
        ).first.click()
        _jupyterlab_ui = (
            page.frame_locator(".qx-main-dark")
            .get_by_label("Untitled.ipynb")
            .get_by_role("textbox")
        )
        _jupyterlab_ui.fill("print('test')")
        _jupyterlab_ui.press("Shift+Enter")
    else:
        msg = "Not supported service key"
        raise ValueError(msg)
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
            resp = api_request_context.delete(
                f"{product_url}v0/projects/{extracted_uuid}"
            )
            assert resp.status == HTTPStatus.NO_CONTENT
