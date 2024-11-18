import contextlib
import json
import logging
import re
from collections import defaultdict
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, unique
from typing import Any, Final

import httpx
from playwright.sync_api import FrameLocator, Page, Request
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import WebSocket
from pydantic import AnyUrl
from pytest_simcore.helpers.logging_tools import log_context

SECOND: Final[int] = 1000
MINUTE: Final[int] = 60 * SECOND
NODE_START_REQUEST_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"/projects/[^/]+/nodes/[^:]+:start"
)


@unique
class RunningState(str, Enum):
    # NOTE: this is a duplicate of models-library/project_states.py
    # It must remain as such until that module is pydantic V2 compatible
    """State of execution of a project's computational workflow

    SEE StateType for task state
    """

    UNKNOWN = "UNKNOWN"
    PUBLISHED = "PUBLISHED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    WAITING_FOR_RESOURCES = "WAITING_FOR_RESOURCES"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    WAITING_FOR_CLUSTER = "WAITING_FOR_CLUSTER"

    def is_running(self) -> bool:
        return self in (
            RunningState.PUBLISHED,
            RunningState.PENDING,
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
            RunningState.WAITING_FOR_CLUSTER,
        )


@unique
class NodeProgressType(str, Enum):
    # NOTE: this is a partial duplicate of models_library/rabbitmq_messages.py
    # It must remain as such until that module is pydantic V2 compatible
    CLUSTER_UP_SCALING = "CLUSTER_UP_SCALING"
    SERVICE_INPUTS_PULLING = "SERVICE_INPUTS_PULLING"
    SIDECARS_PULLING = "SIDECARS_PULLING"
    SERVICE_OUTPUTS_PULLING = "SERVICE_OUTPUTS_PULLING"
    SERVICE_STATE_PULLING = "SERVICE_STATE_PULLING"
    SERVICE_IMAGES_PULLING = "SERVICE_IMAGES_PULLING"
    SERVICE_CONTAINERS_STARTING = "SERVICE_CONTAINERS_STARTING"

    @classmethod
    def required_types_for_started_service(cls) -> set["NodeProgressType"]:
        return {
            NodeProgressType.SERVICE_INPUTS_PULLING,
            NodeProgressType.SIDECARS_PULLING,
            NodeProgressType.SERVICE_OUTPUTS_PULLING,
            NodeProgressType.SERVICE_STATE_PULLING,
            NodeProgressType.SERVICE_IMAGES_PULLING,
            NodeProgressType.SERVICE_CONTAINERS_STARTING,
        }


class ServiceType(str, Enum):
    DYNAMIC = "DYNAMIC"
    COMPUTATIONAL = "COMPUTATIONAL"


class _OSparcMessages(str, Enum):
    NODE_UPDATED = "nodeUpdated"
    NODE_PROGRESS = "nodeProgress"
    PROJECT_STATE_UPDATED = "projectStateUpdated"
    SERVICE_DISK_USAGE = "serviceDiskUsage"
    WALLET_OSPARC_CREDITS_UPDATED = "walletOsparcCreditsUpdated"
    LOGGER = "logger"


@dataclass(frozen=True, slots=True, kw_only=True)
class AutoRegisteredUser:
    user_email: str
    password: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SocketIOEvent:
    name: str
    obj: dict[str, Any]


SOCKETIO_MESSAGE_PREFIX: Final[str] = "42"


def decode_socketio_42_message(message: str) -> SocketIOEvent:
    data = json.loads(message.removeprefix(SOCKETIO_MESSAGE_PREFIX))
    return SocketIOEvent(name=data[0], obj=data[1])


def retrieve_project_state_from_decoded_message(event: SocketIOEvent) -> RunningState:
    assert event.name == _OSparcMessages.PROJECT_STATE_UPDATED.value
    assert "data" in event.obj
    assert "state" in event.obj["data"]
    assert "value" in event.obj["data"]["state"]
    return RunningState(event.obj["data"]["state"]["value"])


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeProgressEvent:
    node_id: str
    progress_type: NodeProgressType
    current_progress: float
    total_progress: float


def retrieve_node_progress_from_decoded_message(
    event: SocketIOEvent,
) -> NodeProgressEvent:
    assert event.name == _OSparcMessages.NODE_PROGRESS.value
    assert "progress_type" in event.obj
    assert "progress_report" in event.obj
    return NodeProgressEvent(
        node_id=event.obj["node_id"],
        progress_type=NodeProgressType(event.obj["progress_type"]),
        current_progress=float(event.obj["progress_report"]["actual_value"]),
        total_progress=float(event.obj["progress_report"]["total"]),
    )


@dataclass
class SocketIOProjectClosedWaiter:
    logger: logging.Logger

    def __call__(self, message: str) -> bool:
        # socket.io encodes messages like so
        # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
        if message.startswith(SOCKETIO_MESSAGE_PREFIX):
            decoded_message = decode_socketio_42_message(message)
            if (
                (decoded_message.name == _OSparcMessages.PROJECT_STATE_UPDATED.value)
                and (decoded_message.obj["data"]["locked"]["status"] == "CLOSED")
                and (decoded_message.obj["data"]["locked"]["value"] is False)
            ):
                self.logger.info("project successfully closed")
                return True

        return False


@dataclass
class SocketIOProjectStateUpdatedWaiter:
    expected_states: tuple[RunningState, ...]

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}"):
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if decoded_message.name == _OSparcMessages.PROJECT_STATE_UPDATED.value:
                    return (
                        retrieve_project_state_from_decoded_message(decoded_message)
                        in self.expected_states
                    )

            return False


@dataclass
class SocketIOOsparcMessagePrinter:
    include_logger_messages: bool = False

    def __call__(self, message: str) -> None:
        osparc_messages = [_.value for _ in _OSparcMessages]
        if not self.include_logger_messages:
            osparc_messages.pop(osparc_messages.index(_OSparcMessages.LOGGER.value))

        if message.startswith(SOCKETIO_MESSAGE_PREFIX):
            decoded_message: SocketIOEvent = decode_socketio_42_message(message)
            if decoded_message.name in osparc_messages:
                print("WS Message:", decoded_message.name, decoded_message.obj)


@dataclass
class SocketIONodeProgressCompleteWaiter:
    node_id: str
    logger: logging.Logger
    product_url: AnyUrl
    _current_progress: dict[NodeProgressType, float] = field(
        default_factory=defaultdict
    )
    _last_poll_timestamp: datetime = datetime.now(tz=UTC)  # noqa: RUF009

    def __call__(self, message: str) -> bool:
        # socket.io encodes messages like so
        # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
        if message.startswith(SOCKETIO_MESSAGE_PREFIX):
            decoded_message = decode_socketio_42_message(message)
            if decoded_message.name == _OSparcMessages.NODE_PROGRESS.value:
                node_progress_event = retrieve_node_progress_from_decoded_message(
                    decoded_message
                )
                if node_progress_event.node_id == self.node_id:
                    new_progress = (
                        node_progress_event.current_progress
                        / node_progress_event.total_progress
                    )
                    if (
                        node_progress_event.progress_type not in self._current_progress
                    ) or (
                        new_progress
                        != self._current_progress[node_progress_event.progress_type]
                    ):
                        self._current_progress[
                            node_progress_event.progress_type
                        ] = new_progress

                        self.logger.info(
                            "Current startup progress [expected number of node-progress-types=%d]: %s",
                            len(NodeProgressType.required_types_for_started_service()),
                            f"{json.dumps({k:round(v,1) for k,v in self._current_progress.items()})}",
                        )

                return self.got_expected_node_progress_types() and all(
                    round(progress, 1) == 1.0
                    for progress in self._current_progress.values()
                )

        _current_timestamp = datetime.now(UTC)
        if _current_timestamp - self._last_poll_timestamp > timedelta(seconds=5):
            url = f"https://{self.node_id}.services.{self.get_partial_product_url()}"
            response = httpx.get(url, timeout=10)
            self.logger.info(
                "Querying the service endpoint from the E2E test. Response: %s, response"
            )
            if response.status_code == 200:
                return True
            self._last_poll_timestamp = datetime.now(UTC)

        return False

    def got_expected_node_progress_types(self):
        return all(
            progress_type in self._current_progress
            for progress_type in NodeProgressType.required_types_for_started_service()
        )

    def get_current_progress(self):
        return self._current_progress.values()

    def get_partial_product_url(self):
        return f"{self.product_url}".split("//")[1]


def wait_for_pipeline_state(
    current_state: RunningState,
    *,
    websocket: WebSocket,
    if_in_states: tuple[RunningState, ...],
    expected_states: tuple[RunningState, ...],
    timeout_ms: int,
) -> RunningState:
    if current_state in if_in_states:
        with log_context(
            logging.INFO,
            msg=(
                f"pipeline is in {current_state=}, waiting for one of {expected_states=}",
                f"pipeline is now in {current_state=}",
            ),
        ):
            waiter = SocketIOProjectStateUpdatedWaiter(expected_states=expected_states)
            with websocket.expect_event(
                "framereceived", waiter, timeout=timeout_ms
            ) as event:
                current_state = retrieve_project_state_from_decoded_message(
                    decode_socketio_42_message(event.value)
                )
    return current_state


@contextlib.contextmanager
def web_socket_default_log_handler(web_socket: WebSocket) -> Iterator[None]:

    try:
        with log_context(
            logging.DEBUG,
            msg="handle websocket message (set to --log-cli-level=DEBUG level if you wanna see all of them)",
        ) as ctx:

            def on_framesent(payload: str | bytes) -> None:
                ctx.logger.debug("⬇️ Frame sent: %s", payload)

            def on_framereceived(payload: str | bytes) -> None:
                ctx.logger.debug("⬆️ Frame received: %s", payload)

            def on_close(payload: WebSocket) -> None:
                ctx.logger.warning("⚠️ Websocket closed: %s", payload)

            def on_socketerror(error_msg: str) -> None:
                ctx.logger.error("❌ Websocket error: %s", error_msg)

            web_socket.on("framesent", on_framesent)
            web_socket.on("framereceived", on_framereceived)
            web_socket.on("close", on_close)
            web_socket.on("socketerror", on_socketerror)
            yield
    finally:
        web_socket.remove_listener("framesent", on_framesent)
        web_socket.remove_listener("framereceived", on_framereceived)
        web_socket.remove_listener("close", on_close)
        web_socket.remove_listener("socketerror", on_socketerror)


def _node_started_predicate(request: Request) -> bool:
    return bool(
        re.search(NODE_START_REQUEST_PATTERN, request.url)
        and request.method.upper() == "POST"
    )


def _trigger_service_start(page: Page, node_id: str) -> None:
    with log_context(logging.INFO, msg="trigger start button"), page.expect_request(
        _node_started_predicate, timeout=35 * SECOND
    ):
        page.get_by_test_id(f"Start_{node_id}").click()


@dataclass(slots=True, kw_only=True)
class ServiceRunning:
    iframe_locator: FrameLocator | None


@contextlib.contextmanager
def expected_service_running(
    *,
    page: Page,
    node_id: str,
    websocket: WebSocket,
    timeout: int,
    press_start_button: bool,
    product_url: AnyUrl,
) -> Generator[ServiceRunning, None, None]:
    with log_context(logging.INFO, msg="Waiting for node to run") as ctx:
        waiter = SocketIONodeProgressCompleteWaiter(
            node_id=node_id, logger=ctx.logger, product_url=product_url
        )
        service_running = ServiceRunning(iframe_locator=None)

        try:

            with websocket.expect_event("framereceived", waiter, timeout=timeout):
                if press_start_button:
                    _trigger_service_start(page, node_id)

                yield service_running

        except PlaywrightTimeoutError:
            if waiter.got_expected_node_progress_types():
                ctx.logger.warning(
                    "⚠️ Progress bar didn't receive 100 percent but all expected node-progress-types are in place: %s ⚠️",  # https://github.com/ITISFoundation/osparc-simcore/issues/6449
                    waiter.get_current_progress(),
                )
            else:
                raise

    service_running.iframe_locator = page.frame_locator(
        f'[osparc-test-id="iframe_{node_id}"]'
    )


def wait_for_service_running(
    *,
    page: Page,
    node_id: str,
    websocket: WebSocket,
    timeout: int,
    press_start_button: bool,
    product_url: AnyUrl,
) -> FrameLocator:
    """NOTE: if the service was already started this will not work as some of the required websocket events will not be emitted again
    In which case this will need further adjutment"""

    with log_context(logging.INFO, msg="Waiting for node to run") as ctx:
        waiter = SocketIONodeProgressCompleteWaiter(
            node_id=node_id, logger=ctx.logger, product_url=product_url
        )
        with websocket.expect_event("framereceived", waiter, timeout=timeout):
            if press_start_button:
                _trigger_service_start(page, node_id)
    return page.frame_locator(f'[osparc-test-id="iframe_{node_id}"]')


def app_mode_trigger_next_app(page: Page) -> None:
    with (
        log_context(logging.INFO, msg="triggering next app"),
        page.expect_request(_node_started_predicate),
    ):
        # Move to next step (this auto starts the next service)
        page.get_by_test_id("AppMode_NextBtn").click()
