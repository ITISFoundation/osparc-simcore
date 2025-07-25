# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

import contextlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Literal

from playwright.sync_api import Page, WebSocket
from pydantic import AnyUrl, ByteSize
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    RobustWebSocket,
    ServiceType,
    wait_for_service_running,
)

_WAITING_FOR_SERVICE_TO_START: Final[int] = (
    10 * MINUTE
)  # NOTE: smash is 13Gib, math 2Gib
_WAITING_TIME_FILE_CREATION_PER_GB_IN_TERMINAL: Final[int] = 10 * SECOND
_DEFAULT_RESPONSE_TO_WAIT_FOR: Final[re.Pattern] = re.compile(
    r"/api/contents/workspace"
)
_SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR: Final[dict[str, re.Pattern]] = {
    "jupyter-octave-python-math": re.compile(r"/api/contents"),  # old way
}

_DEFAULT_TAB_TO_WAIT_FOR: Final[str] = "README.ipynb"
_SERVICE_NAME_TAB_TO_WAIT_FOR: Final[dict[str, str]] = {}


@dataclass
class _JLabTerminalWebSocketWaiter:
    expected_message_type: Literal["stdout", "stdin"]
    expected_message_contents: str

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}"):
            decoded_message = json.loads(message)
            return bool(
                self.expected_message_type == decoded_message[0]
                and self.expected_message_contents in decoded_message[1]
            )


@dataclass
class _JLabWaitForTerminalWebSocket:
    def __call__(self, new_websocket: WebSocket) -> bool:
        with log_context(logging.DEBUG, msg=f"received {new_websocket=}"):
            return "terminals/websocket" in new_websocket.url


def test_jupyterlab(
    page: Page,
    log_in_and_out: RobustWebSocket,
    create_project_from_service_dashboard: Callable[
        [ServiceType, str, str | None, str | None], dict[str, Any]
    ],
    service_key: str,
    service_version: str | None,
    large_file_size: ByteSize,
    large_file_block_size: ByteSize,
    product_url: AnyUrl,
    is_service_legacy: bool,
):
    # NOTE: this waits for the jupyter to send message, but is not quite enough
    with (
        log_context(
            logging.INFO,
            f"Waiting for {service_key} to be responsive (waiting for {_SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR.get(service_key, _DEFAULT_RESPONSE_TO_WAIT_FOR)})",
        ),
        page.expect_response(
            _SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR.get(
                service_key, _DEFAULT_RESPONSE_TO_WAIT_FOR
            ),
            timeout=_WAITING_FOR_SERVICE_TO_START,
        ),
    ):
        project_data = create_project_from_service_dashboard(
            ServiceType.DYNAMIC, service_key, None, service_version
        )
        assert "workbench" in project_data, "Expected workbench to be in project data!"
        assert isinstance(
            project_data["workbench"], dict
        ), "Expected workbench to be a dict!"
        node_ids: list[str] = list(project_data["workbench"])
        assert len(node_ids) == 1, "Expected 1 node in the workbench!"

        wait_for_service_running(
            page=page,
            node_id=node_ids[0],
            websocket=log_in_and_out,
            timeout=_WAITING_FOR_SERVICE_TO_START,
            press_start_button=False,
            product_url=product_url,
            is_service_legacy=is_service_legacy,
        )

    iframe = page.frame_locator("iframe")
    if service_key == "jupyter-octave-python-math":
        print(
            f"skipping any more complicated stuff since this is {service_key=} which is legacy"
        )
        return

    if service_key == "jupyter-ml-pytorch":
        with contextlib.suppress(TimeoutError):
            iframe.get_by_role("button", name="Select", exact=True).click()

    with log_context(
        logging.INFO,
        f"Waiting for {_SERVICE_NAME_TAB_TO_WAIT_FOR.get(service_key, _DEFAULT_TAB_TO_WAIT_FOR)} to become visible",
    ):
        iframe.get_by_role(
            "tab",
            name=_SERVICE_NAME_TAB_TO_WAIT_FOR.get(
                service_key, _DEFAULT_TAB_TO_WAIT_FOR
            ),
        ).wait_for(state="visible")
    if large_file_size:
        with log_context(
            logging.INFO,
            f"Creating multiple files and 1 file of about {large_file_size.human_readable()}",
        ):
            iframe.get_by_role("button", name="New Launcher").nth(0).click()
            with page.expect_websocket(_JLabWaitForTerminalWebSocket()) as ws_info:
                iframe.get_by_label("Launcher").get_by_text("Terminal").click()

            assert not ws_info.value.is_closed()
            restartable_terminal_web_socket = RobustWebSocket(page, ws_info.value)

            terminal = iframe.locator(
                "#jp-Terminal-0 > div > div.xterm-screen"
            ).get_by_role("textbox")
            terminal.fill("pip install uv")
            terminal.press("Enter")
            terminal.fill("uv pip install numpy pandas dask[distributed] fastapi")
            terminal.press("Enter")
            # NOTE: this call creates a large file with random blocks inside
            blocks_count = int(large_file_size / large_file_block_size)
            with restartable_terminal_web_socket.expect_event(
                "framereceived",
                _JLabTerminalWebSocketWaiter(
                    expected_message_type="stdout", expected_message_contents="copied"
                ),
                timeout=_WAITING_TIME_FILE_CREATION_PER_GB_IN_TERMINAL
                * max(int(large_file_size.to("GiB")), 1)
                * 3,  # avoids flakyness since timeout is deterimned based on size
            ):
                terminal.fill(
                    f"dd if=/dev/urandom of=output.txt bs={large_file_block_size} count={blocks_count} iflag=fullblock"
                )
                terminal.press("Enter")

            restartable_terminal_web_socket.auto_reconnect = False

        # NOTE: this is to let some tester see something
        page.wait_for_timeout(2000)

    if service_key == "jupyter-ml-pytorch":
        print(
            f"skipping any more complicated stuff since this is {service_key=} which is different from the others"
        )
        return
    # Wait until iframe is shown and create new notebook with print statement
    with log_context(logging.INFO, "Running new notebook"):
        iframe.get_by_role("button", name="New Launcher").nth(0).click()
        iframe.locator(".jp-LauncherCard-icon").first.click()
        iframe.get_by_role("tab", name="Untitled.ipynb").click()
        _jupyterlab_ui = iframe.get_by_label("Untitled.ipynb").get_by_role("textbox")
        _jupyterlab_ui.fill("print('hello from e2e test')")
        _jupyterlab_ui.press("Shift+Enter")

    page.wait_for_timeout(1000)
