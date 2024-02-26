import json
import logging
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from enum import Enum, unique
from types import SimpleNamespace
from typing import Any, Final, TypeAlias

from playwright.sync_api import WebSocket

SECOND: Final[int] = 1000
MINUTE: Final[int] = 60 * SECOND


class DynamicIndentFormatter(logging.Formatter):
    indent_char: str = "\t"
    _indent_level: int = 0

    def __init__(self, fmt=None, datefmt=None, style="%"):
        dynamic_fmt = fmt or "%(asctime)s %(levelname)s %(message)s"
        assert "message" in dynamic_fmt
        super().__init__(dynamic_fmt, datefmt, style)

    def format(self, record):  # noqa: A003
        original_message = record.msg
        record.msg = f"{self.indent_char * self._indent_level}{original_message}"
        result = super().format(record)
        record.msg = original_message
        return result

    @classmethod
    def increase_indent(cls):
        cls._indent_level += 1

    @classmethod
    def decrease_indent(cls):
        cls._indent_level = max(0, cls._indent_level - 1)

    @classmethod
    def setup(cls, logger: logging.Logger):
        _formatter = DynamicIndentFormatter()
        _handler = logging.StreamHandler()
        _handler.setFormatter(_formatter)
        logger.addHandler(_handler)
        logger.setLevel(logging.INFO)


test_logger = logging.getLogger(__name__)
DynamicIndentFormatter.setup(test_logger)


@dataclass
class ContextMessages:
    starting: str
    done: str
    raised: str = field(default="")

    def __post_init__(self):
        if not self.raised:
            self.raised = f"{self.done} [with error]"


LogLevelInt: TypeAlias = int
LogMessageStr: TypeAlias = str


@contextmanager
def log_context(
    level: LogLevelInt,
    msg: LogMessageStr | tuple | ContextMessages,
    *args,
    logger: logging.Logger = test_logger,
    **kwargs,
) -> Iterator[SimpleNamespace]:
    # NOTE: Preserves original signature of a logger https://docs.python.org/3/library/logging.html#logging.Logger.log
    # NOTE: To add more info to the logs e.g. times, user_id etc prefer using formatting instead of adding more here

    if isinstance(msg, str):
        ctx_msg = ContextMessages(
            starting=f"-> {msg} starting ...",
            done=f"<- {msg} done",
            raised=f"! {msg} raised",
        )
    elif isinstance(msg, tuple):
        ctx_msg = ContextMessages(*msg)
    else:
        ctx_msg = msg

    try:
        DynamicIndentFormatter.increase_indent()

        logger.log(level, ctx_msg.starting, *args, **kwargs)

        yield SimpleNamespace(logger=logger, messages=ctx_msg)

        logger.log(level, ctx_msg.done, *args, **kwargs)

    except:
        logger.log(logging.ERROR, ctx_msg.raised, *args, **kwargs)
        raise

    finally:
        DynamicIndentFormatter.decrease_indent()


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
        # print(f"<---- received websocket {message=}")
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
        waiter = SocketIOProjectStateUpdatedWaiter(expected_states=expected_states)
        print(f"--> pipeline is in {current_state=}, waiting for {expected_states=}")
        with websocket.expect_event(
            "framereceived", waiter, timeout=timeout_ms
        ) as event:
            current_state = retrieve_project_state_from_decoded_message(
                decode_socketio_42_message(event.value)
            )
        print(f"<-- pipeline is in {current_state=}")
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
