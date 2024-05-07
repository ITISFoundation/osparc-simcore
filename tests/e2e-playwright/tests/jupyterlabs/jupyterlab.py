# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import re
from typing import Callable, Final

from playwright.sync_api import APIRequestContext, Page
from pydantic import AnyUrl, ByteSize, TypeAdapter
from pytest_simcore.playwright_utils import RunningState, on_web_socket_default_handler

_PROJECTS_UUID_PATTERN: Final[re.Pattern] = re.compile(
    r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def test_jupyterlab(
    page: Page,
    log_in_and_out: None,
    create_new_project_and_delete: Callable[..., None],
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    product_billable: bool,
    service_key: str,
    large_file_size: ByteSize,
):
    # connect and listen to websocket
    page.on("websocket", on_web_socket_default_handler)

    # open services tab and filter for the service
    page.get_by_test_id("servicesTabBtn").click()
    _textbox = page.get_by_role("textbox", name="search")
    _textbox.fill(service_key)
    _textbox.press("Enter")
    page.get_by_test_id(
        f"studyBrowserListItem_simcore/services/dynamic/{service_key}"
    ).click()

    create_new_project_and_delete(expected_states=(RunningState.UNKNOWN,))

    if large_file_size:

        iframe = page.frame_locator("iframe")
        iframe.get_by_role("menuitem", name="File").click()
        iframe.locator("#jp-mainmenu-file > ul > li:nth-child(2)").click()
        iframe.get_by_label("Launcher").get_by_text("Terminal").click()
        # jp-mainmenu-file > ul > li:nth-child(2)
        # id-4a32be53-8696-4197-bc07-7a6d0045469a > div > div > div:nth-child(4) > div.jp-Launcher-cardContainer > div:nth-child(1)
        terminal = iframe.locator(
            "#jp-Terminal-0 > div > div.xterm-screen"
        ).get_by_role("textbox")
        terminal.fill("pip install uv")
        terminal.press("Enter")
        terminal.fill("uv pip install numpy pandas dask[distributed] fastapi")
        terminal.press("Enter")
        block_size = TypeAdapter(ByteSize).validate_python("64Mib")
        blocks_count = int(large_file_size / block_size)
        terminal.fill(
            f"dd if=/dev/urandom of=output.txt bs={block_size} count={blocks_count} iflag=fullblock"
        )
        terminal.press("Enter")

        page.wait_for_timeout(10000)

    # Wait until iframe is shown and create new notebook with print statement

    page.frame_locator(".qx-main-dark").get_by_role(
        "button", name="New Launcher"
    ).click(timeout=600000)

    # Jupyter smash service
    page.frame_locator(".qx-main-dark").locator(".jp-LauncherCard-icon").first.click()
    page.wait_for_timeout(3000)
    page.frame_locator(".qx-main-dark").get_by_role(
        "tab", name="Untitled.ipynb"
    ).click()
    _jupyterlab_ui = (
        page.frame_locator(".qx-main-dark")
        .get_by_label("Untitled.ipynb")
        .get_by_role("textbox")
    )
    _jupyterlab_ui.fill("print('test')")
    _jupyterlab_ui.press("Shift+Enter")

    page.wait_for_timeout(1000)
