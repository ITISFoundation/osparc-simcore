# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import logging
import re
from collections.abc import Callable
from typing import Final

from playwright.sync_api import Page
from pydantic import ByteSize
from pytest_simcore.logging_utils import log_context
from pytest_simcore.playwright_utils import MINUTE, ServiceType

_WAITING_FOR_SERVICE_TO_START: Final[int] = (
    10 * MINUTE
)  # NOTE: smash is 13Gib, math 2Gib

_SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR: Final[dict[str, re.Pattern]] = {
    "jupyter-math": re.compile(r"/api/contents/workspace"),
    "jupyter-smash": re.compile(r"/api/contents/workspace"),
    "jupyter-octave-python-math": re.compile(r"/api/contents"),
}

_SERVICE_NAME_TAB_TO_WAIT_FOR: Final[dict[str, str]] = {
    "jupyter-math": "README.ipynb",
    "jupyter-smash": "README.ipynb",
}


def test_jupyterlab(
    page: Page,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None], str
    ],
    service_key: str,
    large_file_size: ByteSize,
    large_file_block_size: ByteSize,
):
    # NOTE: this waits for the jupyter to send message, but is not quite enough
    with log_context(
        logging.INFO, f"Waiting for {service_key} responsive"
    ), page.expect_response(
        _SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR[service_key],
        timeout=_WAITING_FOR_SERVICE_TO_START,
    ):
        create_project_from_service_dashboard(ServiceType.DYNAMIC, service_key, None)

    iframe = page.frame_locator("iframe")
    if service_key == "jupyter-octave-python-math":
        print(
            f"skipping any more complicated stuff since this is {service_key=} which is legacy"
        )
        return

    with log_context(
        logging.INFO,
        f"Waiting for {_SERVICE_NAME_TAB_TO_WAIT_FOR[service_key]} to become visible",
    ):
        iframe.get_by_role(
            "tab", name=_SERVICE_NAME_TAB_TO_WAIT_FOR[service_key]
        ).wait_for(state="visible")
    if large_file_size:
        with log_context(
            logging.INFO,
            f"Creating multiple files and 1 file of about {large_file_size.human_readable()}",
        ):
            iframe.get_by_role("button", name="New Launcher").click()
            iframe.get_by_label("Launcher").get_by_text("Terminal").click()
            terminal = iframe.locator(
                "#jp-Terminal-0 > div > div.xterm-screen"
            ).get_by_role("textbox")
            terminal.fill("pip install uv")
            terminal.press("Enter")
            terminal.fill("uv pip install numpy pandas dask[distributed] fastapi")
            terminal.press("Enter")
            # NOTE: this call creates a large file with random blocks inside
            blocks_count = int(large_file_size / large_file_block_size)
            terminal.fill(
                f"dd if=/dev/urandom of=output.txt bs={large_file_block_size} count={blocks_count} iflag=fullblock"
            )
            terminal.press("Enter")

        # NOTE: this is to let some tester see something
        page.wait_for_timeout(2000)

    # Wait until iframe is shown and create new notebook with print statement
    with log_context(logging.INFO, "Running new notebook"):
        iframe.get_by_role("button", name="New Launcher").click()
        iframe.locator(".jp-LauncherCard-icon").first.click()
        iframe.get_by_role("tab", name="Untitled.ipynb").click()
        _jupyterlab_ui = iframe.get_by_label("Untitled.ipynb").get_by_role("textbox")
        _jupyterlab_ui.fill("print('hello from e2e test')")
        _jupyterlab_ui.press("Shift+Enter")

    page.wait_for_timeout(1000)
