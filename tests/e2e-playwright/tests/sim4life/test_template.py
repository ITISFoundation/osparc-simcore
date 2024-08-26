# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import datetime
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import arrow
from playwright.sync_api import Page, WebSocket, expect
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import (
    MINUTE,
    SECOND,
    SOCKETIO_MESSAGE_PREFIX,
    SocketIOEvent,
    decode_socketio_42_message,
    wait_for_service_running,
)

projects_uuid_pattern: Final[re.Pattern] = re.compile(
    r"/projects/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)
_EC2_STARTUP_MAX_WAIT_TIME: Final[int] = 1 * MINUTE
_S4L_MAX_STARTUP_TIME: Final[int] = 1 * MINUTE
_S4L_DOCKER_PULLING_MAX_TIME: Final[int] = 10 * MINUTE
_S4L_AUTOSCALED_MAX_STARTUP_TIME: Final[int] = (
    _EC2_STARTUP_MAX_WAIT_TIME + _S4L_DOCKER_PULLING_MAX_TIME + _S4L_MAX_STARTUP_TIME
)

_S4L_STARTUP_SCREEN_MAX_TIME: Final[int] = 45 * SECOND
_S4L_STREAMING_ESTABLISHMENT_MAX_TIME: Final[int] = 15 * SECOND


_S4L_SOCKETIO_REGEX: Final[re.Pattern] = re.compile(
    r"^(?P<protocol>[^:]+)://(?P<node_id>[^\.]+)\.services\.(?P<hostname>[^\/]+)\/socket\.io\/.+$"
)


@dataclass(kw_only=True)
class _S4LWaitForWebsocket:
    logger: logging.Logger

    def __call__(self, new_websocket: WebSocket) -> bool:
        if re.match(_S4L_SOCKETIO_REGEX, new_websocket.url):
            self.logger.info("found S4L websocket!")
            return True

        return False


@dataclass
class _S4LSocketIOMessagePrinter:
    def __call__(self, message: str) -> None:
        if message.startswith(SOCKETIO_MESSAGE_PREFIX):
            decoded_message: SocketIOEvent = decode_socketio_42_message(message)
            print("S4L WS Message:", decoded_message.name, decoded_message.obj)


@dataclass(kw_only=True)
class _S4LSocketIOCheckBitRateIncreasesMessagePrinter:
    observation_time: datetime.timedelta
    logger: logging.Logger
    _initial_bit_rate: float = 0
    _initial_bit_rate_time: datetime.datetime = arrow.utcnow().datetime

    def __call__(self, message: str) -> bool:
        if message.startswith(SOCKETIO_MESSAGE_PREFIX):
            decoded_message: SocketIOEvent = decode_socketio_42_message(message)
            if (
                decoded_message.name == "server.video_stream.bitrate_data"
                and "bitrate" in decoded_message.obj
            ):
                current_bitrate = decoded_message.obj["bitrate"]
                if self._initial_bit_rate == 0:
                    self._initial_bit_rate = current_bitrate
                    self._initial_bit_rate_time = arrow.utcnow().datetime
                    self.logger.info(
                        "%s",
                        f"{self._initial_bit_rate=} at {self._initial_bit_rate_time.isoformat()}",
                    )
                    return False

                # NOTE: MaG says the value might also go down, but it shall definitely change,
                # if this code proves unsafe we should change it.
                elapsed_time = arrow.utcnow().datetime - self._initial_bit_rate_time
                if (
                    elapsed_time > self.observation_time
                    and "bitrate" in decoded_message.obj
                ):
                    current_bitrate = decoded_message.obj["bitrate"]
                    bitrate_test = bool(self._initial_bit_rate != current_bitrate)
                    self.logger.info(
                        "%s",
                        f"{current_bitrate=} after {elapsed_time=}: {'good!' if bitrate_test else 'failed! bitrate did not change! TIP: talk with MaG about underwater cables!'}",
                    )
                    return bitrate_test

        return False


def test_template(
    page: Page,
    create_project_from_template_dashboard: Callable[[str], dict[str, Any]],
    log_in_and_out: WebSocket,
    # OM Fix this
    # template_id: str,
    autoscaled: bool,
    check_videostreaming: bool,
):
    # OM Fix this
    template_id = "776cdc9a-6125-11ef-abcf-02420a00f199"
    project_data = create_project_from_template_dashboard(template_id)
    assert "workbench" in project_data, "Expected workbench to be in project data!"
    assert isinstance(
        project_data["workbench"], dict
    ), "Expected workbench to be a dict!"
    node_ids: list[str] = list(project_data["workbench"])
    assert len(node_ids) == 1, "Expected 1 node in the workbench!"

    with log_context(logging.INFO, "launch S4L") as ctx:
        predicate = _S4LWaitForWebsocket(logger=ctx.logger)
        with page.expect_websocket(
            predicate,
            timeout=_S4L_STARTUP_SCREEN_MAX_TIME
            + (
                _S4L_AUTOSCALED_MAX_STARTUP_TIME
                if autoscaled
                else _S4L_MAX_STARTUP_TIME
            )
            + 10 * SECOND,
        ) as ws_info:
            s4l_iframe = wait_for_service_running(
                page=page,
                node_id=node_ids[0],
                websocket=log_in_and_out,
                timeout=(
                    _S4L_AUTOSCALED_MAX_STARTUP_TIME
                    if autoscaled
                    else _S4L_MAX_STARTUP_TIME
                ),
                press_start_button=False,
            )
        s4l_websocket = ws_info.value
        ctx.logger.info("acquired S4L websocket!")

    # Wait until grid is shown
    # NOTE: the startup screen should disappear very fast after the websocket was acquired
    with log_context(logging.INFO, "Interact with S4l"):
        s4l_iframe.get_by_test_id("tree-item-Grid").nth(0).click()
    page.wait_for_timeout(3000)

    if check_videostreaming:
        with log_context(logging.INFO, "Check videostreaming works") as ctx:
            waiter = _S4LSocketIOCheckBitRateIncreasesMessagePrinter(
                observation_time=datetime.timedelta(
                    milliseconds=_S4L_STREAMING_ESTABLISHMENT_MAX_TIME / 2.0,
                ),
                logger=ctx.logger,
            )
            with s4l_websocket.expect_event(
                "framereceived",
                waiter,
                timeout=_S4L_STREAMING_ESTABLISHMENT_MAX_TIME,
            ):
                ...

            expect(
                s4l_iframe.locator("video"),
                "videostreaming is not established. "
                "TIP: if using playwright integrated open source chromIUM, "
                "webkit or firefox this is expected, switch to chrome/msedge!!",
            ).to_be_visible()
            s4l_iframe.locator("video").click()
        page.wait_for_timeout(3000)
