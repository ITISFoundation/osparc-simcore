import contextlib
import json
import logging
import re
from collections import defaultdict
from contextlib import ExitStack
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Final

from playwright.sync_api import FrameLocator, Page, Request, WebSocket, expect
from pytest_simcore.helpers.logging import log_context

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

    @classmethod
    def required_types_for_started_service(cls) -> set["NodeProgressType"]:
        return {
            NodeProgressType.SERVICE_INPUTS_PULLING,
            NodeProgressType.SIDECARS_PULLING,
            NodeProgressType.SERVICE_OUTPUTS_PULLING,
            NodeProgressType.SERVICE_STATE_PULLING,
            NodeProgressType.SERVICE_IMAGES_PULLING,
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


_SOCKETIO_MESSAGE_PREFIX: Final[str] = "42"


def decode_socketio_42_message(message: str) -> SocketIOEvent:
    data = json.loads(message.removeprefix(_SOCKETIO_MESSAGE_PREFIX))
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
    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}"):
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(_SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if (
                    (
                        decoded_message.name
                        == _OSparcMessages.PROJECT_STATE_UPDATED.value
                    )
                    and (decoded_message.obj["data"]["locked"]["status"] == "CLOSED")
                    and (decoded_message.obj["data"]["locked"]["value"] is False)
                ):
                    return True

            return False


@dataclass
class SocketIOProjectStateUpdatedWaiter:
    expected_states: tuple[RunningState, ...]

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}"):
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(_SOCKETIO_MESSAGE_PREFIX):
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

        if message.startswith(_SOCKETIO_MESSAGE_PREFIX):
            decoded_message: SocketIOEvent = decode_socketio_42_message(message)
            if decoded_message.name in osparc_messages:
                print("WS Message:", decoded_message.name, decoded_message.obj)


@dataclass
class SocketIONodeProgressCompleteWaiter:
    node_id: str
    _current_progress: dict[NodeProgressType, float] = field(
        default_factory=defaultdict
    )

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(_SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if decoded_message.name == _OSparcMessages.NODE_PROGRESS.value:
                    node_progress_event = retrieve_node_progress_from_decoded_message(
                        decoded_message
                    )
                    if node_progress_event.node_id == self.node_id:
                        self._current_progress[node_progress_event.progress_type] = (
                            node_progress_event.current_progress
                            / node_progress_event.total_progress
                        )
                        ctx.logger.info(
                            "current startup progress: %s",
                            f"{json.dumps({k:round(v,1) for k,v in self._current_progress.items()})}",
                        )

                    return all(
                        progress_type in self._current_progress
                        for progress_type in NodeProgressType.required_types_for_started_service()
                    ) and all(
                        round(progress, 1) == 1.0
                        for progress in self._current_progress.values()
                    )

            return False


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


def on_web_socket_default_handler(ws) -> None:
    """Usage

    from pytest_simcore.playwright_utils import on_web_socket_default_handler

    page.on("websocket", on_web_socket_default_handler)

    """
    stack = ExitStack()
    ctx = stack.enter_context(
        log_context(
            logging.INFO,
            (
                f"WebSocket opened: {ws.url}",
                "WebSocket closed",
            ),
        )
    )

    ws.on("framesent", lambda payload: ctx.logger.info("⬇️ %s", payload))
    ws.on("framereceived", lambda payload: ctx.logger.info("⬆️ %s", payload))
    ws.on("close", lambda payload: stack.close())  # noqa: ARG005


def _node_started_predicate(request: Request) -> bool:
    return bool(
        re.search(NODE_START_REQUEST_PATTERN, request.url)
        and request.method.upper() == "POST"
    )


def _trigger_service_start_if_button_available(page: Page, node_id: str) -> None:
    # wait for the start button to auto-disappear if it is still around after the timeout, then we click it
    with log_context(logging.INFO, msg="trigger start button if needed") as ctx:
        start_button_locator = page.get_by_test_id(f"Start_{node_id}")
        with contextlib.suppress(AssertionError, TimeoutError):
            expect(start_button_locator).to_be_visible(timeout=5000)
            expect(start_button_locator).to_be_enabled(timeout=5000)
            with page.expect_request(_node_started_predicate):
                start_button_locator.click()
                ctx.logger.info("triggered start button")


def wait_for_service_running(
    *,
    page: Page,
    node_id: str,
    websocket: WebSocket,
    timeout: int,
) -> FrameLocator:
    """NOTE: if the service was already started this will not work as some of the required websocket events will not be emitted again
    In which case this will need further adjutment"""

    waiter = SocketIONodeProgressCompleteWaiter(node_id=node_id)
    with (
        log_context(logging.INFO, msg="Waiting for node to run"),
        websocket.expect_event("framereceived", waiter, timeout=timeout),
    ):
        _trigger_service_start_if_button_available(page, node_id)
    return page.frame_locator(f'[osparc-test-id="iframe_{node_id}"]')


def app_mode_trigger_next_app(page: Page) -> None:
    with (
        log_context(logging.INFO, msg="triggering next app"),
        page.expect_request(_node_started_predicate),
    ):
        # Move to next step (this auto starts the next service)
        next_button_locator = page.get_by_test_id("AppMode_NextBtn")
        if next_button_locator.is_visible() and next_button_locator.is_enabled():
            page.get_by_test_id("AppMode_NextBtn").click()
