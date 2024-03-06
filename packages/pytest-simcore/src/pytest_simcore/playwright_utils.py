import json
import logging
from contextlib import ExitStack
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Final

from playwright.sync_api import WebSocket
from pytest_simcore.logging_utils import log_context

SECOND: Final[int] = 1000
MINUTE: Final[int] = 60 * SECOND


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


@dataclass(frozen=True, slots=True, kw_only=True)
class AutoRegisteredUser:
    user_email: str
    password: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SocketIOEvent:
    name: str
    obj: dict[str, Any]


def decode_socketio_42_message(message: str) -> SocketIOEvent:
    data = json.loads(message.removeprefix("42"))
    return SocketIOEvent(name=data[0], obj=data[1])


def retrieve_project_state_from_decoded_message(event: SocketIOEvent) -> RunningState:
    assert event.name == "projectStateUpdated"
    assert "data" in event.obj
    assert "state" in event.obj["data"]
    assert "value" in event.obj["data"]["state"]
    return RunningState(event.obj["data"]["state"]["value"])


@dataclass
class SocketIOProjectStateUpdatedWaiter:
    expected_states: tuple[RunningState, ...]

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}"):
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith("42"):
                decoded_message = decode_socketio_42_message(message)
                if decoded_message.name == "projectStateUpdated":
                    return (
                        retrieve_project_state_from_decoded_message(decoded_message)
                        in self.expected_states
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
    ws.on("close", lambda payload: stack.close())
