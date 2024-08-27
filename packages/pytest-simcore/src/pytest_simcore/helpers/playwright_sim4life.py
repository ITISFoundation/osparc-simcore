import datetime
import logging
import re
from dataclasses import dataclass
from typing import Final

import arrow
from playwright.sync_api import Page, WebSocket, expect

from .logging_tools import log_context
from .playwright import (
    SECOND,
    SOCKETIO_MESSAGE_PREFIX,
    SocketIOEvent,
    decode_socketio_42_message,
)

_S4L_STREAMING_ESTABLISHMENT_MAX_TIME: Final[int] = 15 * SECOND
_S4L_SOCKETIO_REGEX: Final[re.Pattern] = re.compile(
    r"^(?P<protocol>[^:]+)://(?P<node_id>[^\.]+)\.services\.(?P<hostname>[^\/]+)\/socket\.io\/.+$"
)


@dataclass(kw_only=True)
class S4LWaitForWebsocket:
    logger: logging.Logger

    def __call__(self, new_websocket: WebSocket) -> bool:
        if re.match(_S4L_SOCKETIO_REGEX, new_websocket.url):
            self.logger.info("found S4L websocket!")
            return True

        return False


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


def check_video_streaming(page: Page, s4l_iframe, s4l_websocket: WebSocket) -> None:
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
