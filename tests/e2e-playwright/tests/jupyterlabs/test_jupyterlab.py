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

from helpers_jupyter_code import create_files_in_jupyter
from models_library.services_enums import ServiceType
from playwright.sync_api import Page, WebSocket, expect
from pydantic import AnyUrl, ByteSize
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    RobustWebSocket,
    _get_service_url,
    wait_for_service_running,
)

_WAITING_FOR_SERVICE_TO_START: Final[int] = 10 * MINUTE  # NOTE: smash is 13Gib, math 2Gib
_DEFAULT_RESPONSE_TO_WAIT_FOR: Final[re.Pattern] = re.compile(r"/api/contents/workspace")
_SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR: Final[dict[str, re.Pattern]] = {
    "jupyter-octave-python-math": re.compile(r"/api/contents"),  # old way
}

_DEFAULT_TAB_TO_WAIT_FOR: Final[str] = "README.ipynb"
_SERVICE_NAME_TAB_TO_WAIT_FOR: Final[dict[str, str]] = {}
_WAITING_FOR_TAB_TO_APPEAR: Final[int] = 1 * MINUTE


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
    create_project_from_service_dashboard: Callable[[ServiceType, str, str | None, str | None], dict[str, Any]],
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
            f"Waiting for {service_key} to be responsive (waiting for "
            f"{_SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR.get(service_key, _DEFAULT_RESPONSE_TO_WAIT_FOR)})",
        ),
        page.expect_response(
            _SERVICE_NAME_EXPECTED_RESPONSE_TO_WAIT_FOR.get(service_key, _DEFAULT_RESPONSE_TO_WAIT_FOR),
            timeout=_WAITING_FOR_SERVICE_TO_START,
        ),
    ):
        project_data = create_project_from_service_dashboard(ServiceType.DYNAMIC, service_key, None, service_version)
        assert "workbench" in project_data, "Expected workbench to be in project data!"
        assert isinstance(project_data["workbench"], dict), "Expected workbench to be a dict!"
        node_ids: list[str] = list(project_data["workbench"])
        assert len(node_ids) == 1, "Expected 1 node in the workbench!"

        iframe = wait_for_service_running(
            page=page,
            node_id=node_ids[0],
            websocket=log_in_and_out,
            timeout=_WAITING_FOR_SERVICE_TO_START,
            press_start_button=False,
            product_url=product_url,
            is_service_legacy=is_service_legacy,
        )

    if service_key == "jupyter-octave-python-math":
        print(f"skipping any more complicated stuff since this is {service_key=} which is legacy")
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
            name=_SERVICE_NAME_TAB_TO_WAIT_FOR.get(service_key, _DEFAULT_TAB_TO_WAIT_FOR),
        ).wait_for(state="visible", timeout=_WAITING_FOR_TAB_TO_APPEAR)
    if large_file_size:
        create_files_in_jupyter(iframe, large_file_size, large_file_block_size)
        # NOTE: this is to let some tester see something
        page.wait_for_timeout(2000)

    if service_key == "jupyter-ml-pytorch":
        print(f"skipping any more complicated stuff since this is {service_key=} which is different from the others")
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

    # Adding a file to outputs/output_1 must add it to the node's Outputs, and deleting
    # it must remove it again without a page refresh
    # (regression test for https://github.com/ITISFoundation/osparc-simcore/issues/9918)
    _output_filename = "e2e-output-check.txt"
    _service_url = f"{_get_service_url(node_ids[0], product_url, is_legacy_service=False)}"
    _xsrf = next(
        (c["value"] for c in page.context.cookies(_service_url) if c["name"] == "_xsrf"),
        "",
    )
    _headers = {"Referer": f"{_service_url}/", "_xsrf": _xsrf}
    with log_context(logging.INFO, f"Creating {_output_filename} in outputs/output_1"):
        page.get_by_test_id("outputsBtn").click()
        response = page.request.put(
            f"{_service_url}/api/contents/outputs/output_1/{_output_filename}",
            headers=_headers,
            data={"type": "file", "format": "text", "content": "created by the e2e test"},
        )
        assert response.ok, f"failed to create file in outputs: {response.status} {response.text()}"
        expect(page.get_by_text(_output_filename)).to_be_visible(timeout=5 * MINUTE)
    with log_context(logging.INFO, f"Deleting {_output_filename} from outputs/output_1"):
        response = page.request.delete(
            f"{_service_url}/api/contents/outputs/output_1/{_output_filename}",
            headers=_headers,
        )
        assert response.ok, f"failed to delete file in outputs: {response.status} {response.text()}"
        expect(page.get_by_text(_output_filename)).to_be_hidden(timeout=2 * MINUTE)
