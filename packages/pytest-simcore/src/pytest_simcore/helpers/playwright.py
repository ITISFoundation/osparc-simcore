# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-instance-attributes
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import contextlib
import json
import logging
import re
import typing
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, unique
from types import TracebackType
from typing import Any, Final

import arrow
import pytest
from playwright._impl._sync_base import EventContextManager, EventInfo
from playwright.sync_api import APIRequestContext, FrameLocator, Locator, Page, Request, WebSocket
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyUrl, TypeAdapter
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_exponential_jitter,
    wait_fixed,
)

from .logging_tools import ContextMessages, log_context

_logger = logging.getLogger(__name__)


SECOND: Final[int] = 1000
MINUTE: Final[int] = 60 * SECOND
NODE_START_REQUEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"/projects/[^/]+/nodes/[^:]+:start")
_APP_MODE_NEXT_APP_START_REQUEST_TIMEOUT: Final[int] = 5 * SECOND


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
    SIDECARS_PULLING = "SIDECARS_PULLING"
    SERVICE_INPUTS_PULLING = "SERVICE_INPUTS_PULLING"
    SERVICE_OUTPUTS_PULLING = "SERVICE_OUTPUTS_PULLING"
    SERVICE_STATE_PULLING = "SERVICE_STATE_PULLING"
    SERVICE_IMAGES_PULLING = "SERVICE_IMAGES_PULLING"
    SERVICE_CONTAINERS_STARTING = "SERVICE_CONTAINERS_STARTING"
    SERVICE_STATE_PUSHING = "SERVICE_STATE_PUSHING"
    SERVICE_OUTPUTS_PUSHING = "SERVICE_OUTPUTS_PUSHING"
    PROJECT_CLOSING = "PROJECT_CLOSING"

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
    SERVICE_STATUS = "serviceStatus"


@dataclass(frozen=True, slots=True, kw_only=True)
class AutoRegisteredUser:
    user_email: str
    password: str


@dataclass(frozen=True, slots=True, kw_only=True)
class SocketIOEvent:
    name: str
    obj: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps({"name": self.name, "obj": self.obj})


SOCKETIO_MESSAGE_PREFIX: Final[str] = "42"
_WEBSOCKET_MESSAGE_PREFIX: Final[str] = "📡OSPARC-WEBSOCKET: "
_SOCKET_CLOSED_ERROR_MESSAGE: Final[str] = "Socket closed"
_MAX_REATTACH_ATTEMPTS: Final[int] = 100


@dataclass
class _ReconnectableEventWaiter:
    """Wraps `WebSocket.expect_event()` so a pending wait survives `RobustWebSocket`
    reconnections instead of raising a stale ``Socket closed`` error.
    """

    robust_websocket: "RobustWebSocket"
    event: str
    predicate: typing.Callable | None
    timeout: float | None

    _deadline: datetime | None = field(init=False, default=None)
    _reattach_attempts: int = field(init=False, default=0)

    _ctx: EventContextManager | None = field(init=False, default=None)
    _event_info: EventInfo | None = field(init=False, default=None)
    _bound_ws: WebSocket = field(init=False)

    def __post_init__(self) -> None:
        if self.timeout is not None:
            self._deadline = datetime.now(UTC) + timedelta(milliseconds=self.timeout)
        self._attach()

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        # NOTE: This pattern avoids `Error: Socked closed` from being raised.
        # If nothing went wrong, read `.value` here so a dropped connection is retried
        # even if the caller never reads `.value` themselves.
        if exc_val is not None:
            if self._ctx is not None:
                self._ctx.__exit__(exc_type, exc_val, exc_tb)
        else:
            _ = self.value

    @property
    def value(self) -> typing.Any:
        """returns the same value as `EventInfo.value` making the result of `socket.expect_event` behave similarly"""

        assert self._event_info is not None  # nosec
        while True:
            try:
                return self._event_info.value
            except PlaywrightError as exc:
                if _SOCKET_CLOSED_ERROR_MESSAGE not in f"{exc}" or self.robust_websocket.ws is self._bound_ws:
                    raise

                self._enforce_reattach_limit(exc)
                with log_context(
                    logging.INFO,
                    msg=f"Reattaching wait for {self.event!r} to newly reconnected websocket",
                ):
                    self._attach()

    def _enforce_reattach_limit(self, exc: PlaywrightError) -> None:
        self._reattach_attempts += 1
        if self._reattach_attempts > _MAX_REATTACH_ATTEMPTS:
            msg = (
                f"Giving up reattaching after {_MAX_REATTACH_ATTEMPTS} attempts while waiting for {self.event!r}. "
                "TIP: please check for networking issues"
            )
            raise PlaywrightError(msg) from exc

    def _remaining_timeout(self) -> float | None:
        if self._deadline is None:
            return None
        return (self._deadline - datetime.now(UTC)).total_seconds() * SECOND

    def _attach(self) -> None:  # pylint: disable=attribute-defined-outside-init,access-member-before-definition
        if self._ctx is not None:
            # Exit the context on the connection we're replacing, as if the `with` block around
            # it had raised - this cancels its pending future instead of blocking on it.
            self._ctx.__exit__(PlaywrightError, PlaywrightError("Reattaching to a new connection"), None)

        self._bound_ws = self.robust_websocket.ws
        remaining_timeout = self._remaining_timeout()
        if remaining_timeout is not None and remaining_timeout <= 0:
            # Playwright treats timeout=0 as "wait forever", so an already-expired
            # deadline must raise here instead of being passed through as-is.
            msg = f"Timeout {self.timeout}ms exceeded while waiting for {self.event!r}."
            raise PlaywrightTimeoutError(msg)

        self._ctx = self._bound_ws.expect_event(self.event, self.predicate, timeout=remaining_timeout)
        self._event_info = self._ctx.__enter__()


@dataclass
class RobustWebSocket:
    page: Page
    ws: WebSocket
    _num_reconnections: int = 0
    auto_reconnect: bool = True

    def __post_init__(self) -> None:
        self._configure_websocket_events()

    def _configure_websocket_events(self) -> None:
        with log_context(
            logging.INFO,
            msg="handle websocket message (set to --log-cli-level=DEBUG level if you wanna see all of them)",
        ) as ctx:

            def on_framesent(payload: str | bytes) -> None:
                ctx.logger.debug("%s⬇️ Frame sent: %s", _WEBSOCKET_MESSAGE_PREFIX, payload)

            def on_framereceived(payload: str | bytes) -> None:
                ctx.logger.debug("%s⬆️ Frame received: %s", _WEBSOCKET_MESSAGE_PREFIX, payload)

            def on_close(_: WebSocket) -> None:
                if self.auto_reconnect:
                    ctx.logger.warning(
                        "%s⚠️ WebSocket closed. Attempting to reconnect...",
                        _WEBSOCKET_MESSAGE_PREFIX,
                    )
                    self._attempt_reconnect(ctx.logger)
                else:
                    ctx.logger.info("%s WebSocket closed.", _WEBSOCKET_MESSAGE_PREFIX)

            def on_socketerror(error_msg: str) -> None:
                ctx.logger.error("%s❌ WebSocket error: %s", _WEBSOCKET_MESSAGE_PREFIX, error_msg)

            # Attach core event listeners
            self.ws.on("framesent", on_framesent)
            self.ws.on("framereceived", on_framereceived)
            self.ws.on("close", on_close)
            self.ws.on("socketerror", on_socketerror)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            max=10,
        ),
        reraise=True,
        before_sleep=before_sleep_log(_logger, logging.WARNING),
    )
    def _attempt_reconnect(self, logger: logging.Logger) -> None:
        """
        Attempt to reconnect the WebSocket and restore event listeners.
        """
        with self.page.expect_websocket(timeout=5000) as ws_info:
            assert not ws_info.value.is_closed()

        self.ws = ws_info.value
        self._num_reconnections += 1
        logger.info(
            "🔄 Reconnected to WebSocket successfully. Number of reconnections: %s",
            self._num_reconnections,
        )
        self._configure_websocket_events()

    def expect_event(
        self,
        event: str,
        predicate: typing.Callable | None = None,
        *,
        timeout: float | None = None,
    ) -> _ReconnectableEventWaiter:
        """
        Register an event listener that keeps waiting across reconnections.
        """
        return _ReconnectableEventWaiter(robust_websocket=self, event=event, predicate=predicate, timeout=timeout)


def decode_socketio_42_message(message: str) -> SocketIOEvent:
    data = json.loads(message.removeprefix(SOCKETIO_MESSAGE_PREFIX))
    return SocketIOEvent(name=data[0], obj=data[1])


def retrieve_project_state_from_decoded_message(event: SocketIOEvent) -> RunningState:
    assert event.name == _OSparcMessages.PROJECT_STATE_UPDATED.value
    assert "data" in event.obj
    assert "state" in event.obj["data"]
    assert "value" in event.obj["data"]["state"]
    return RunningState(event.obj["data"]["state"]["value"])


def retrieve_project_id_from_decoded_message(event: SocketIOEvent) -> str:
    assert event.name == _OSparcMessages.PROJECT_STATE_UPDATED.value
    assert "project_uuid" in event.obj
    return event.obj["project_uuid"]


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
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if (
                    (decoded_message.name == _OSparcMessages.PROJECT_STATE_UPDATED.value)
                    and (decoded_message.obj["data"]["shareState"]["status"] == "CLOSED")
                    and (decoded_message.obj["data"]["shareState"]["locked"] is False)
                ):
                    ctx.logger.info("project successfully closed")
                    return True

        return False


@dataclass
class SocketIOProjectStateUpdatedWaiter:
    expected_states: tuple[RunningState, ...]
    project_uuid: str | None = None

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if decoded_message.name == _OSparcMessages.PROJECT_STATE_UPDATED.value:
                    if self.project_uuid is None:
                        ctx.logger.warning("ignoring projectStateUpdated because waiter.project_uuid is not set yet")
                        return False

                    message_project_uuid = retrieve_project_id_from_decoded_message(decoded_message)
                    if message_project_uuid != self.project_uuid:
                        # a different project (e.g. a previous test/job's project still open or
                        # closing on the shared user): ignore it and keep waiting for ours
                        ctx.logger.debug(
                            "ignoring projectStateUpdated for other project %s (waiting for %s)",
                            message_project_uuid,
                            self.project_uuid,
                        )
                        return False
                    return retrieve_project_state_from_decoded_message(decoded_message) in self.expected_states

            return False


@dataclass
class SocketIOWaitNodeForOutputs:
    expected_number_of_outputs: int
    node_id: str

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if decoded_message.name == _OSparcMessages.NODE_UPDATED:
                    assert "data" in decoded_message.obj
                    assert "node_id" in decoded_message.obj
                    if decoded_message.obj["node_id"] == self.node_id:
                        # NOTE: NodeUpdated is also sent for state-only changes (e.g. PUBLISHED),
                        # which carry no "outputs" key at all
                        outputs = decoded_message.obj["data"].get("outputs")
                        if outputs is not None:
                            is_complete = len(outputs) == self.expected_number_of_outputs
                            if is_complete:
                                ctx.logger.info(
                                    "📤 outputs push received for node %s (%d/%d)",
                                    self.node_id,
                                    len(outputs),
                                    self.expected_number_of_outputs,
                                )
                            return is_complete

        return False


@dataclass
class SocketIOWaitNodesForOutputs:
    """Like `SocketIOWaitNodeForOutputs`, but resolves only once *every* node in
    `node_id_to_expected_number_of_outputs` has reported its expected number of outputs
    (e.g. several nodes completing concurrently in the same pipeline run).
    """

    node_id_to_expected_number_of_outputs: dict[str, int]
    _pending_node_ids: set[str] = field(init=False)
    _received_number_of_outputs: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        self._pending_node_ids = set(self.node_id_to_expected_number_of_outputs)
        self._received_number_of_outputs = {}

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if decoded_message.name == _OSparcMessages.NODE_UPDATED:
                    assert "data" in decoded_message.obj
                    assert "node_id" in decoded_message.obj
                    node_id = decoded_message.obj["node_id"]
                    if node_id in self._pending_node_ids:
                        # NOTE: NodeUpdated is also sent for state-only changes (e.g. PUBLISHED),
                        # which carry no "outputs" key at all
                        outputs = decoded_message.obj["data"].get("outputs")
                        if outputs is not None:
                            self._received_number_of_outputs[node_id] = len(outputs)
                            expected = self.node_id_to_expected_number_of_outputs[node_id]
                            if len(outputs) == expected:
                                self._pending_node_ids.discard(node_id)
                                ctx.logger.info(
                                    "📤 outputs push received for node %s (%d/%d), %d node(s) left",
                                    node_id,
                                    len(outputs),
                                    expected,
                                    len(self._pending_node_ids),
                                )

        return not self._pending_node_ids

    def missing_outputs_report(self) -> str:
        """Reports, for each node still pending, how many outputs were received vs expected."""
        return ", ".join(
            f"{node_id}: {self._received_number_of_outputs.get(node_id, 0)}/{expected}"
            for node_id, expected in self.node_id_to_expected_number_of_outputs.items()
            if node_id in self._pending_node_ids
        )


@contextlib.contextmanager
def wait_for_nodes_outputs_updated(
    websocket: RobustWebSocket,
    *,
    node_id_to_expected_number_of_outputs: dict[str, int],
    timeout: int | None = None,
) -> Generator[None]:
    """Asserts that a `NodeUpdated` websocket message with the expected number of outputs is
    received for every node in `node_id_to_expected_number_of_outputs` while the wrapped block
    runs. Unlike `check_node_outputs` (which only polls the REST API after the fact), this
    verifies the websocket push actually happened.
    """
    waiter = SocketIOWaitNodesForOutputs(node_id_to_expected_number_of_outputs=node_id_to_expected_number_of_outputs)
    with (
        log_context(
            logging.INFO,
            msg=ContextMessages(
                starting=f"⏳ waiting for outputs push for nodes {list(node_id_to_expected_number_of_outputs)}",
                done="✅ received outputs push for all expected nodes",
                raised=lambda: (
                    f"❌ missing outputs push for: {waiter.missing_outputs_report()}. "
                    "TIP: check that the webserver's db-listener service is running properly!"
                ),
            ),
        ),
        websocket.expect_event("framereceived", waiter, timeout=timeout),
    ):
        yield


_FAIL_FAST_DYNAMIC_SERVICE_STATES: Final[tuple[str, ...]] = ("failed",)
# NOTE: right after a service start is requested, the dynamic-scheduler may still
# report "idle" for a short while (it has not yet picked up the start request).
# This is expected and must not be treated as a failure immediately.
_MIN_IDLE_DURATION_BEFORE_FAIL_FAST: Final[timedelta] = timedelta(seconds=15)
_SERVICE_ROOT_POINT_STATUS_TIMEOUT: Final[timedelta] = timedelta(seconds=30)


def _get_service_url(node_id: str, product_url: AnyUrl, *, is_legacy_service: bool) -> AnyUrl:
    port_suffix = f":{product_url.port}" if product_url.port else ""
    return TypeAdapter(AnyUrl).validate_python(
        f"{product_url.scheme}://{product_url.host}{port_suffix}/x/{node_id}"
        if is_legacy_service
        else f"{product_url.scheme}://{node_id}.services.{product_url.host}{port_suffix}"
    )


def _check_service_endpoint(
    node_id: str,
    *,
    api_request_context: APIRequestContext,
    logger: logging.Logger,
    product_url: AnyUrl,
    is_legacy_service: bool,
) -> bool:
    # NOTE: we might have missed some websocket messages, and we check if the service is ready
    service_url = _get_service_url(node_id, product_url, is_legacy_service=is_legacy_service)

    with log_context(
        logging.INFO,
        "Check service endpoint: %s",
        service_url,
    ):
        response = None

        try:
            response = api_request_context.get(
                f"{service_url}",
                timeout=_SERVICE_ROOT_POINT_STATUS_TIMEOUT.total_seconds() * SECOND,
            )
        except (PlaywrightTimeoutError, TimeoutError):
            logger.exception(
                "❌ Timed-out requesting service endpoint after %ds ❌",
                _SERVICE_ROOT_POINT_STATUS_TIMEOUT,
            )
        except PlaywrightError:
            logger.exception("Failed to request service endpoint")
        else:
            # NOTE: 502,503 are acceptable if the service is not yet ready (traefik still setting up)
            if response.status in (502, 503):
                logger.info("⏳ service not ready yet %s ⏳", f"{response.status=}")
                return False
            if response.status > 400:
                logger.error(
                    "❌ service responded with error: %s:%s ❌",
                    f"{response.status}",
                    f"{response.text()}",
                )
                return False

            if response.status <= 400:
                # NOTE: If the response status is less than 400, it means that the service is ready (There are some services that respond with a 3XX)
                logger.info("✅ Service ready!! responded with %s ✅", f"{response.status=}")
                return True
    return False


_SOCKET_IO_NODE_PROGRESS_WAITER_MAX_IDLE_TIMEOUT: Final[timedelta] = timedelta(seconds=60)


def _evaluate_service_status(
    obj: dict[str, Any],
    *,
    node_id: str,
    first_service_status_received_at: datetime | None,
    min_idle_before_fail_fast: timedelta,
    logger: logging.Logger,
) -> tuple[bool | None, datetime | None]:
    """Returns a tuple of:
    - True/False if the waiter is resolved by this SERVICE_STATUS message, or
      None if it does not concern this node and should be ignored
    - the (possibly updated) first_service_status_received_at timestamp
    """
    if obj["service_uuid"] != node_id:
        return None, first_service_status_received_at

    if first_service_status_received_at is None:
        first_service_status_received_at = datetime.now(UTC)

    service_state = obj["service_state"]
    if service_state in _FAIL_FAST_DYNAMIC_SERVICE_STATES:
        # NOTE: this is a fail fast for dynamic services that fail to start
        logger.error(
            "❌ node %s failed with state %s, failing fast ❌",
            node_id,
            service_state,
        )
        return True, first_service_status_received_at

    if service_state == "idle":
        elapsed_since_first_status = datetime.now(UTC) - first_service_status_received_at
        if elapsed_since_first_status >= min_idle_before_fail_fast:
            # NOTE: the service is still idle well after it was first observed
            logger.error(
                "❌ node %s still idle %s since first status (>= %s grace period), failing fast ❌",
                node_id,
                elapsed_since_first_status,
                min_idle_before_fail_fast,
            )
            return True, first_service_status_received_at
        logger.info(
            "⏳ node %s idle %s since first status (within %s grace period), still waiting ⏳",
            node_id,
            elapsed_since_first_status,
            min_idle_before_fail_fast,
        )
        return False, first_service_status_received_at

    return None, first_service_status_received_at


@dataclass
class SocketIONodeProgressCompleteWaiter:
    node_id: str
    max_idle_timeout: timedelta = _SOCKET_IO_NODE_PROGRESS_WAITER_MAX_IDLE_TIMEOUT
    min_idle_before_fail_fast: timedelta = _MIN_IDLE_DURATION_BEFORE_FAIL_FAST
    _current_progress: dict[NodeProgressType, float] = field(default_factory=defaultdict)
    _last_progress_time: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    _received_messages: list[SocketIOEvent] = field(default_factory=list)

    _first_service_status_received_at: datetime | None = None
    _result: bool = False

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                self._received_messages.append(decoded_message)
                if decoded_message.name == _OSparcMessages.SERVICE_STATUS.value:
                    service_status_resolved, self._first_service_status_received_at = _evaluate_service_status(
                        decoded_message.obj,
                        node_id=self.node_id,
                        first_service_status_received_at=self._first_service_status_received_at,
                        min_idle_before_fail_fast=self.min_idle_before_fail_fast,
                        logger=ctx.logger,
                    )
                    if service_status_resolved is True:
                        # NOTE: reaching this point always means a fail-fast (see _evaluate_service_status)
                        self._result = False
                        return True
                if decoded_message.name == _OSparcMessages.NODE_PROGRESS.value:
                    node_progress_event = retrieve_node_progress_from_decoded_message(decoded_message)
                    if node_progress_event.node_id == self.node_id:
                        new_progress = node_progress_event.current_progress / node_progress_event.total_progress
                        self._last_progress_time = datetime.now(UTC)
                        if (node_progress_event.progress_type not in self._current_progress) or (
                            new_progress != self._current_progress[node_progress_event.progress_type]
                        ):
                            self._current_progress[node_progress_event.progress_type] = new_progress

                            ctx.logger.info(
                                "Current startup progress [expected %d types]: %s",
                                len(NodeProgressType.required_types_for_started_service()),
                                f"{json.dumps({k: round(v, 2) for k, v in self._current_progress.items()})}",
                            )

                    done = self._completed_successfully()
                    if done:
                        self._result = True  # NOTE: might have failed but it is not sure. so we set the result to True
                        ctx.logger.info("✅ Service start completed successfully!! ✅")
                    return done

            time_since_last_progress = datetime.now(UTC) - self._last_progress_time
            if time_since_last_progress > self.max_idle_timeout:
                ctx.logger.warning(
                    "⚠️ %s passed since the last received progress message. "
                    "The service %s might be stuck, or we missed some messages ⚠️",
                    time_since_last_progress,
                    self.node_id,
                )
                self._result = True
                return True

            return False

    def _completed_successfully(self) -> bool:
        return all(
            progress_type in self._current_progress
            for progress_type in NodeProgressType.required_types_for_started_service()
        ) and all(round(progress, 1) == 1.0 for progress in self._current_progress.values())

    @property
    def success(self) -> bool:
        return self._result


def wait_for_service_endpoint_responding(
    node_id: str,
    *,
    api_request_context: APIRequestContext,
    product_url: AnyUrl,
    is_legacy_service: bool,
    timeout: int = 30 * SECOND,
) -> None:
    """emulates the frontend polling for the service endpoint until it responds with 2xx/3xx"""

    @retry(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(timeout / 1000),
        before_sleep=before_sleep_log(_logger, logging.INFO),
        reraise=True,
    )
    def _retry_check_service_endpoint(logger: logging.Logger) -> None:
        is_service_ready = _check_service_endpoint(
            node_id,
            api_request_context=api_request_context,
            logger=logger,
            product_url=product_url,
            is_legacy_service=is_legacy_service,
        )
        assert is_service_ready, "❌ the service failed starting! ❌"

    with log_context(
        logging.INFO, msg=f"wait for service endpoint to be ready ({timedelta(milliseconds=timeout)})"
    ) as ctx:
        _retry_check_service_endpoint(ctx.logger)


_FAIL_FAST_COMPUTATIONAL_STATES: Final[tuple[RunningState, ...]] = (
    RunningState.FAILED,
    RunningState.ABORTED,
)


def wait_for_pipeline_state(
    current_state: RunningState,
    *,
    websocket: RobustWebSocket,
    if_in_states: tuple[RunningState, ...],
    expected_states: tuple[RunningState, ...],
    timeout_ms: int,
) -> RunningState:
    if current_state in if_in_states:
        with log_context(
            logging.INFO,
            msg=ContextMessages(
                starting=f"wait for one of {expected_states=} (timeout {timedelta(milliseconds=timeout_ms)})",
                done=lambda: f"wait for one of {expected_states=}, pipeline reached {current_state=}",
                raised=lambda: f"pipeline failed or timed out with {current_state}. Expected one of {expected_states=}",
            ),
        ):
            waiter = SocketIOProjectStateUpdatedWaiter(
                expected_states=expected_states + _FAIL_FAST_COMPUTATIONAL_STATES
            )
            with websocket.expect_event("framereceived", waiter, timeout=timeout_ms) as event:
                current_state = retrieve_project_state_from_decoded_message(decode_socketio_42_message(event.value))
            if current_state in _FAIL_FAST_COMPUTATIONAL_STATES and current_state not in expected_states:
                pytest.fail(f"❌ Pipeline failed fast with state {current_state}. Expected one of {expected_states} ❌")
    return current_state


_RUNNING_STATES: Final[tuple[RunningState, ...]] = (
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_CLUSTER,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
)

_RUN_PIPELINE_MAX_WAIT_TIME: Final[int] = 60 * SECOND
_COMPUTATION_START_REQUEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"/computations")
_COMPUTATION_START_REQUEST_TIMEOUT: Final[int] = 35 * SECOND


def _computation_started_predicate(request: Request) -> bool:
    return bool(re.search(_COMPUTATION_START_REQUEST_PATTERN, request.url) and request.method.upper() == "POST")


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineStageTimeouts:
    """Per-transition timeout budgets for a staged pipeline wait.

    Needed for autoscaled deployments, where a cold cluster/worker scale-up can take several
    minutes without the pipeline actually being stuck. Mirrors the legacy sleepers state machine:
    PUBLISHED/PENDING -> [WAITING_FOR_CLUSTER] -> [WAITING_FOR_RESOURCES] -> STARTED -> SUCCESS
    """

    published_or_pending_ms: int = 1 * MINUTE
    waiting_for_cluster_ms: int = 5 * MINUTE
    waiting_for_resources_ms: int = 5 * MINUTE
    started_ms: int = 5 * MINUTE

    @property
    def total_ms(self) -> int:
        """Upper bound covering every stage sequentially, for wrappers spanning the whole wait."""
        return (
            self.published_or_pending_ms + self.waiting_for_cluster_ms + self.waiting_for_resources_ms + self.started_ms
        )


def wait_for_computation_done(
    current_state: RunningState,
    *,
    websocket: RobustWebSocket,
    stage_timeouts: PipelineStageTimeouts | int,
) -> RunningState:
    """Waits for an already-started computational pipeline to reach a final state.

    Pass an ``int`` for a single flat timeout budget covering the whole run (simple/
    non-autoscaled deployments), or a `PipelineStageTimeouts` to instead wait through each
    transition with its own budget (autoscaled deployments).
    """
    if isinstance(stage_timeouts, int):
        return wait_for_pipeline_state(
            current_state,
            websocket=websocket,
            if_in_states=_RUNNING_STATES,
            expected_states=(RunningState.SUCCESS,),
            timeout_ms=stage_timeouts,
        )

    current_state = wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        if_in_states=(RunningState.PUBLISHED, RunningState.PENDING),
        expected_states=(
            RunningState.WAITING_FOR_CLUSTER,
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
            RunningState.SUCCESS,
        ),
        timeout_ms=stage_timeouts.published_or_pending_ms,
    )
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        if_in_states=(RunningState.WAITING_FOR_CLUSTER,),
        expected_states=(
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
            RunningState.SUCCESS,
        ),
        timeout_ms=stage_timeouts.waiting_for_cluster_ms,
    )
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        if_in_states=(RunningState.WAITING_FOR_RESOURCES,),
        expected_states=(
            RunningState.STARTED,
            RunningState.SUCCESS,
        ),
        timeout_ms=stage_timeouts.waiting_for_resources_ms,
    )
    return wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        if_in_states=(RunningState.STARTED,),
        expected_states=(RunningState.SUCCESS,),
        timeout_ms=stage_timeouts.started_ms,
    )


def run_pipeline_and_wait_done(
    page: Page,
    websocket: RobustWebSocket,
    *,
    run_button_test_id: str = "runStudyBtn",
    timeout_ms: int = _RUN_PIPELINE_MAX_WAIT_TIME,
    stage_timeouts: PipelineStageTimeouts | None = None,
) -> RunningState:
    """Clicks the "Run" button and waits until the pipeline reaches a final state.

    By default (``stage_timeouts=None``) this waits within a single ``timeout_ms`` budget. Pass
    ``stage_timeouts`` to instead wait through each transition with its own budget, needed for
    autoscaled deployments (see `PipelineStageTimeouts`).

    Port of the legacy `TutorialBase.runPipeline()` + `TutorialBase.waitForStudyDone()`.
    """
    # NOTE: mirrors `start_and_stop_pipeline` (tests/conftest.py): expected_states is restricted to
    # the "actively running" states only (no NOT_STARTED/UNKNOWN/SUCCESS/FAILED/ABORTED) so a stray
    # `projectStateUpdated` frame still reporting the pre-run state can't race with the actual run
    # trigger and be mistaken for a final state; the `POST /computations` request is also checked
    # to confirm the click really triggered a computation.
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=_RUNNING_STATES)
    with log_context(
        logging.INFO,
        f"Running pipeline and waiting for it to complete (timeout {timedelta(milliseconds=timeout_ms)})",
    ) as ctx:
        with (
            websocket.expect_event("framereceived", waiter, timeout=timeout_ms) as event,
            page.expect_request(
                _computation_started_predicate, timeout=_COMPUTATION_START_REQUEST_TIMEOUT
            ) as request_info,
        ):
            page.get_by_test_id(run_button_test_id).click()
        response = request_info.value.response()
        assert response
        ctx.logger.info("POST /computations request response: %s", f"{response.status=}")
        assert response.ok, f"{response.json()}"
        current_state = retrieve_project_state_from_decoded_message(decode_socketio_42_message(event.value))
        current_state = wait_for_computation_done(
            current_state,
            websocket=websocket,
            stage_timeouts=stage_timeouts if stage_timeouts is not None else timeout_ms,
        )
        assert current_state == RunningState.SUCCESS, f"❌ Pipeline finished with {current_state} ❌"
        return current_state


def _node_started_predicate(request: Request) -> bool:
    return bool(re.search(NODE_START_REQUEST_PATTERN, request.url) and request.method.upper() == "POST")


def _trigger_service_start(page: Page, node_id: str) -> None:
    with (
        log_context(logging.INFO, msg="trigger start button"),
        page.expect_request(_node_started_predicate, timeout=35 * SECOND),
    ):
        page.get_by_test_id(f"Start_{node_id}").click()


@dataclass(slots=True, kw_only=True)
class ServiceRunning:
    iframe_locator: FrameLocator | None


_MIN_TIMEOUT_WAITING_FOR_SERVICE_ENDPOINT: Final[int] = 30 * SECOND


def _service_iframe_locator(page: Page, node_id: str) -> FrameLocator:
    """Returns the service iframe for ``node_id``, resilient to duplicate iframes."""
    iframe_selector = f'[osparc-test-id="iframe_{node_id}"]'
    iframe_count = page.locator(iframe_selector).count()
    if iframe_count > 1:
        _logger.warning(
            "Found %d iframes with duplicate osparc-test-id for node %s; using the first one "
            "(see ITISFoundation/osparc-simcore#9541)",
            iframe_count,
            node_id,
        )
    return page.frame_locator(iframe_selector).first


@contextlib.contextmanager
def expected_service_running(
    *,
    page: Page,
    node_id: str,
    websocket: RobustWebSocket,
    timeout: int,
    press_start_button: bool,
    product_url: AnyUrl,
    is_service_legacy: bool,
) -> Generator[ServiceRunning]:
    started = arrow.utcnow()
    with contextlib.ExitStack() as stack:
        ctx = stack.enter_context(
            log_context(
                logging.INFO,
                msg=f"Waiting for node to run. Timeout: {timedelta(milliseconds=timeout)}",
            )
        )

        if is_service_legacy:
            waiter = None
            ctx.logger.info("⚠️ Legacy service detected. We are skipping websocket messages in this case! ⚠️")
        else:
            waiter = SocketIONodeProgressCompleteWaiter(
                node_id=node_id,
                max_idle_timeout=min(
                    _SOCKET_IO_NODE_PROGRESS_WAITER_MAX_IDLE_TIMEOUT,
                    timedelta(seconds=timeout / 1000 - 10),
                ),
            )
            stack.enter_context(websocket.expect_event("framereceived", waiter, timeout=timeout))
        service_running = ServiceRunning(iframe_locator=None)
        if press_start_button:
            _trigger_service_start(page, node_id)
        yield service_running

    elapsed_time = arrow.utcnow() - started
    if waiter and not waiter.success:
        pytest.fail("❌ Service failed starting!  ❌")

    wait_for_service_endpoint_responding(
        node_id,
        api_request_context=page.request,
        product_url=product_url,
        is_legacy_service=is_service_legacy,
        timeout=max(
            timeout - int(elapsed_time.total_seconds() * SECOND),
            _MIN_TIMEOUT_WAITING_FOR_SERVICE_ENDPOINT,
        ),
    )
    service_running.iframe_locator = _service_iframe_locator(page, node_id)


def wait_for_service_running(
    *,
    page: Page,
    node_id: str,
    websocket: RobustWebSocket,
    timeout: int,
    press_start_button: bool,
    product_url: AnyUrl,
    is_service_legacy: bool,
) -> FrameLocator:
    """NOTE: if the service was already started this will not work as some of
    the required websocket events will not be emitted again.
    In which case this will need further adjustment
    """

    started = arrow.utcnow()
    with contextlib.ExitStack() as stack:
        ctx = stack.enter_context(
            log_context(
                logging.INFO,
                msg=f"Waiting for node to run. Timeout: {timedelta(milliseconds=timeout)}",
            )
        )
        if is_service_legacy:
            waiter = None
            ctx.logger.info("⚠️ Legacy service detected. We are skipping websocket messages in this case! ⚠️")
        else:
            waiter = SocketIONodeProgressCompleteWaiter(
                node_id=node_id,
                max_idle_timeout=min(
                    _SOCKET_IO_NODE_PROGRESS_WAITER_MAX_IDLE_TIMEOUT,
                    timedelta(seconds=timeout / 1000 - 10),
                ),
            )
            stack.enter_context(websocket.expect_event("framereceived", waiter, timeout=timeout))
        if press_start_button:
            _trigger_service_start(page, node_id)
    elapsed_time = arrow.utcnow() - started

    if waiter and not waiter.success:
        pytest.fail("❌ Service failed starting!  ❌")

    wait_for_service_endpoint_responding(
        node_id,
        api_request_context=page.request,
        product_url=product_url,
        is_legacy_service=is_service_legacy,
        timeout=max(
            timeout - int(elapsed_time.total_seconds() * SECOND),
            _MIN_TIMEOUT_WAITING_FOR_SERVICE_ENDPOINT,
        ),
    )

    return _service_iframe_locator(page, node_id)


def app_mode_trigger_next_app(page: Page) -> None:
    """NOTE: the frontend only issues a node `:start` request if the next
    service is not already running (see `Node.canNodeStart()` in the
    frontend). If the next service was already started, clicking "Next"
    will not fire that request, so we tolerate the timeout here and let the
    caller's websocket-based waiters handle the already-running case.
    """
    with log_context(logging.INFO, msg="triggering next app") as ctx:
        try:
            with page.expect_request(_node_started_predicate, timeout=_APP_MODE_NEXT_APP_START_REQUEST_TIMEOUT):
                # Move to next step (this auto starts the next service)
                page.get_by_test_id("AppMode_NextBtn").click()
        except (PlaywrightTimeoutError, TimeoutError):
            ctx.logger.info(
                "⚠️ no start request detected within %s ms: the next service was likely already started ⚠️",
                _APP_MODE_NEXT_APP_START_REQUEST_TIMEOUT,
            )


def wait_for_label_text(page: Page, locator: str, substring: str, timeout: int = 10000) -> Locator:
    page.locator(locator).wait_for(state="visible", timeout=timeout)

    page.wait_for_function(
        f"() => document.querySelector('{locator}').innerText.includes('{substring}')",
        timeout=timeout,
    )

    return page.locator(locator)


def get_node_id_from_service_key(workbench: dict[str, Any], service_key_fragment: str) -> str:
    """Finds the node id in a project's workbench whose service key contains the given fragment."""
    for node_id, node_data in workbench.items():
        if service_key_fragment in node_data["key"]:
            return node_id
    msg = f"Could not find a node with service key containing {service_key_fragment!r} in workbench"
    raise ValueError(msg)


def get_node_id_from_label(workbench: dict[str, Any], label_fragment: str) -> str:
    """Finds the node id in a project's workbench whose label contains the given fragment.

    Preferred over the workbench tree's displayed text since the workbench dict is the
    authoritative source for a node's label.
    """
    matches = [node_id for node_id, node_data in workbench.items() if label_fragment in node_data["label"]]
    available_labels = [node_data["label"] for node_data in workbench.values()]
    if not matches:
        msg = f"Could not find a node with label containing {label_fragment!r} (available: {available_labels})"
        raise ValueError(msg)
    if len(matches) > 1:
        msg = f"Found {len(matches)} nodes with label containing {label_fragment!r} (available: {available_labels})"
        raise ValueError(msg)
    return matches[0]


def get_node_id_from_position(workbench: dict[str, Any], position: int) -> str:
    """Returns the node id at `position` in the workbench (its insertion order).

    Preferred over the workbench tree's DOM order since the workbench dict is the authoritative
    source for a project's nodes and their order.
    """
    node_ids = list(workbench)
    assert 0 <= position < len(node_ids), f"position {position} out of range for workbench with {len(node_ids)} node(s)"
    return node_ids[position]


def _select_node(page: Page, *, node_id: str) -> None:
    """Selects the node with `node_id` in the workbench tree (left panel)."""
    locator = page.locator(f'[osparc-test-id="nodeTreeItem"][osparc-test-key="{node_id}"]')
    assert locator.count() == 1, f"expected exactly one tree item for node {node_id!r}, found {locator.count()}"
    locator.click()


_OUTPUT_FILE_NAMES_MAX_WAITING_TIME: Final[timedelta] = timedelta(seconds=30)
_OUTPUT_FILE_NAMES_WAIT_INTERVAL: Final[timedelta] = timedelta(seconds=5)


def _read_output_file_names(
    page: Page,
    *,
    node_id: str,
    path_filter: str,
    expected_file_names: list[str],
    open_outputs_folder: bool,
) -> list[str]:
    # the frontend may still be rendering the file list right after the outputs API responds, so
    # this is retried until it matches (or times out). NOTE: the mismatch case is expected/routine
    # here, so it's kept out of `log_context` to avoid logging a full traceback on every retry.
    page.get_by_test_id("folderGridView").click()
    items = page.get_by_test_id("FolderViewerItem")

    if open_outputs_folder:
        outputs_found = False
        for index in range(items.count()):
            item = items.nth(index)
            if "output" in (item.text_content() or ""):
                item.dblclick()
                outputs_found = True
        assert outputs_found, f"outputs folder not found for node {node_id} ({path_filter})"
        items = page.get_by_test_id("FolderViewerItem")

    actual_file_names = sorted([(name or "").removesuffix("\ue24d") for name in items.all_text_contents()])
    missing_file_names = sorted(set(expected_file_names) - set(actual_file_names))
    unexpected_file_names = sorted(set(actual_file_names) - set(expected_file_names))
    if missing_file_names or unexpected_file_names:
        msg = f"Node {node_id} outputs not ready yet: missing={missing_file_names} unexpected={unexpected_file_names}"
        raise AssertionError(msg)

    _logger.info("✅ Node %s outputs match expected file names: %s", node_id, actual_file_names)
    return actual_file_names


@retry(
    stop=stop_after_delay(_OUTPUT_FILE_NAMES_MAX_WAITING_TIME),
    retry=retry_if_exception_type(AssertionError),
    reraise=True,
    wait=wait_exponential_jitter(max=_OUTPUT_FILE_NAMES_WAIT_INTERVAL.total_seconds()),
    before_sleep=before_sleep_log(_logger, logging.INFO),
)
def _check_node_outputs_dialog(
    page: Page,
    *,
    study_id: str,
    node_id: str,
    expected_file_names: list[str],
    open_outputs_folder: bool,
    app_mode: bool,
) -> None:
    with log_context(logging.INFO, "Opening node outputs panel"):
        path_filter = f"{study_id}/{node_id}"
        with page.expect_response(
            re.compile(r"storage/locations/0/paths\?file_filter="),
            timeout=_OUTPUT_FILE_NAMES_MAX_WAITING_TIME.total_seconds() * 1000,
        ):
            if app_mode:
                page.get_by_test_id("outputsBtn").click()
            page.get_by_test_id("nodeFilesBtn").click()

    try:
        _read_output_file_names(
            page,
            node_id=node_id,
            path_filter=path_filter,
            expected_file_names=expected_file_names,
            open_outputs_folder=open_outputs_folder,
        )
    finally:
        with log_context(logging.INFO, "Closing node outputs panel"):
            page.get_by_test_id("nodeDataManagerCloseBtn").click()


def check_node_outputs(
    page: Page,
    *,
    study_id: str,
    workbench: dict[str, Any],
    node_position: int | None = None,
    node_name: str | None = None,
    node_id: str | None = None,
    expected_file_names: list[str],
    open_outputs_folder: bool = False,
    app_mode: bool = False,
) -> None:
    """Opens a node's output files panel and asserts it contains exactly `expected_file_names`.

    The node is identified by exactly one of `node_id`, `node_position` (its index in
    `workbench`) or `node_name` (its label in `workbench`). `workbench` is the project's
    authoritative source of node ids/labels/order, so the lookup never depends on the fragile
    workbench tree's DOM order/displayed text.

    Port of the legacy `TutorialBase.checkNodeOutputs()` /
    `TutorialBase.checkNodeOutputsAppMode()`.
    """
    if node_id is None:
        assert (node_position is None) != (node_name is None), (
            "either node_id, node_position or node_name must be provided"
        )
        if node_position is not None:
            node_id = get_node_id_from_position(workbench, node_position)
        else:
            assert node_name is not None
            node_id = get_node_id_from_label(workbench, node_name)
    assert node_id in workbench, f"node {node_id!r} not found in workbench"
    _select_node(page, node_id=node_id)

    with log_context(logging.INFO, f"Checking node {node_id=} outputs"):
        _check_node_outputs_dialog(
            page,
            study_id=study_id,
            node_id=node_id,
            expected_file_names=expected_file_names,
            open_outputs_folder=open_outputs_folder,
            app_mode=app_mode,
        )
