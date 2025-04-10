# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-instance-attributes

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
from pathlib import Path
from typing import Any, Final

import pytest
from playwright._impl._sync_base import EventContextManager
from playwright.sync_api import (
    APIRequestContext,
)
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import (
    FrameLocator,
    Locator,
    Page,
    Request,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import (
    WebSocket,
)
from pydantic import AnyUrl, TypeAdapter
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
)

from .logging_tools import log_context

_logger = logging.getLogger(__name__)


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


@dataclass
class RobustWebSocket:
    page: Page
    ws: WebSocket
    _registered_events: list[tuple[str, typing.Callable | None]] = field(
        default_factory=list
    )
    _num_reconnections: int = 0

    def __post_init__(self):
        self._configure_websocket_events()

    def _configure_websocket_events(self):
        with log_context(
            logging.INFO,
            msg="handle websocket message (set to --log-cli-level=DEBUG level if you wanna see all of them)",
        ) as ctx:

            def on_framesent(payload: str | bytes) -> None:
                ctx.logger.debug("⬇️ Frame sent: %s", payload)

            def on_framereceived(payload: str | bytes) -> None:
                ctx.logger.debug("⬆️ Frame received: %s", payload)

            def on_close(_: WebSocket) -> None:
                ctx.logger.warning("⚠️ WebSocket closed. Attempting to reconnect...")
                self._attempt_reconnect(ctx.logger)

            def on_socketerror(error_msg: str) -> None:
                ctx.logger.error("❌ WebSocket error: %s", error_msg)

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
        # Re-register all custom event listeners
        for event, predicate in self._registered_events:
            self.ws.expect_event(event, predicate)

    def expect_event(
        self,
        event: str,
        predicate: typing.Callable | None = None,
        *,
        timeout: float | None = None,
    ) -> EventContextManager:
        """
        Register an event listener with support for reconnection.
        """
        output = self.ws.expect_event(event, predicate, timeout=timeout)
        self._registered_events.append((event, predicate))
        return output


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


_FAIL_FAST_DYNAMIC_SERVICE_STATES: Final[tuple[str, ...]] = ("idle", "failed")
_SERVICE_ROOT_POINT_STATUS_TIMEOUT: Final[timedelta] = timedelta(seconds=5)


def _get_service_url(
    node_id: str, product_url: AnyUrl, *, is_legacy_service: bool
) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(
        f"{product_url.scheme}://{product_url.host}/x/{node_id}"
        if is_legacy_service
        else f"{product_url.scheme}://{node_id}.services.{product_url.host}"
    )
    return f"{product_url}".split("//")[1]


def _check_service_endpoint(
    node_id: str,
    *,
    api_request_context: APIRequestContext,
    logger: logging.Logger,
    product_url: AnyUrl,
    is_legacy_service: bool,
) -> bool:
    # NOTE: we might have missed some websocket messages, and we check if the service is ready
    service_url = _get_service_url(
        node_id, product_url, is_legacy_service=is_legacy_service
    )

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
                "Timed-out requesting service endpoint after %ds",
                _SERVICE_ROOT_POINT_STATUS_TIMEOUT,
            )
        except PlaywrightError:
            logger.exception("Failed to request service endpoint")
        else:
            # NOTE: 502,503 are acceptable if the service is not yet ready (traefik still setting up)
            if response.status in (502, 503):
                logger.info("service not ready yet %s", f"{response.status=}")
                return False
            if response.status > 400:
                logger.error(
                    "service responded with error: %s:%s",
                    f"{response.status}",
                    f"{response.text()}",
                )
                return False

            if response.status <= 400:
                # NOTE: If the response status is less than 400, it means that the service is ready (There are some services that respond with a 3XX)
                logger.info(
                    "✅ Service ready!! respondedd with %s ✅", f"{response.status=}"
                )
                return True
    return False


@dataclass
class SocketIONodeProgressCompleteWaiter:
    node_id: str
    logger: logging.Logger
    product_url: AnyUrl
    api_request_context: APIRequestContext
    is_service_legacy: bool
    assertion_output_folder: Path
    _current_progress: dict[NodeProgressType, float] = field(
        default_factory=defaultdict
    )
    _last_poll_timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    _received_messages: list[SocketIOEvent] = field(default_factory=list)

    def __call__(self, message: str) -> bool:
        # socket.io encodes messages like so
        # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
        if message.startswith(SOCKETIO_MESSAGE_PREFIX):
            decoded_message = decode_socketio_42_message(message)
            self._received_messages.append(decoded_message)
            if (
                (decoded_message.name == _OSparcMessages.SERVICE_STATUS.value)
                and (decoded_message.obj["service_uuid"] == self.node_id)
                and (
                    decoded_message.obj["service_state"]
                    in _FAIL_FAST_DYNAMIC_SERVICE_STATES
                )
            ):
                # NOTE: this is a fail fast for dynamic services that fail to start
                self.logger.error(
                    "node %s failed with state %s, failing fast",
                    self.node_id,
                    decoded_message.obj["service_state"],
                )
                return True
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
                        self._current_progress[node_progress_event.progress_type] = (
                            new_progress
                        )

                        self.logger.info(
                            "Current startup progress [expected %d types]: %s",
                            len(NodeProgressType.required_types_for_started_service()),
                            f"{json.dumps({k: round(v, 2) for k, v in self._current_progress.items()})}",
                        )
                return self.got_expected_node_progress_types() and all(
                    round(progress, 1) == 1.0
                    for progress in self._current_progress.values()
                )

        _current_timestamp = datetime.now(UTC)
        if (
            _current_timestamp - self._last_poll_timestamp
            > _SERVICE_ROOT_POINT_STATUS_TIMEOUT
        ):
            self._last_poll_timestamp = datetime.now(UTC)
            if _check_service_endpoint(
                self.node_id,
                api_request_context=self.api_request_context,
                logger=self.logger,
                product_url=self.product_url,
                is_legacy_service=self.is_service_legacy,
            ):
                self.logger.warning(
                    "⚠️ Progress bar did not complete. TIP: some websocket messages were missed! ⚠️",  # https://github.com/ITISFoundation/osparc-simcore/issues/6449
                )
                return True

        return False

    def got_expected_node_progress_types(self) -> bool:
        return all(
            progress_type in self._current_progress
            for progress_type in NodeProgressType.required_types_for_started_service()
        )

    @property
    def number_received_messages(self) -> int:
        return len(self._received_messages)


@retry(
    retry=retry_if_exception_type(AssertionError),
    wait=wait_fixed(1),
    stop=stop_after_delay(30),
    before_sleep=before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
def wait_for_service_ready(
    node_id: str,
    *,
    api_request_context: APIRequestContext,
    logger: logging.Logger,
    product_url: AnyUrl,
    is_legacy_service: bool,
) -> None:
    """emulates the frontend polling for the service endpoint until it responds with 2xx/3xx"""
    is_service_ready = _check_service_endpoint(
        node_id,
        api_request_context=api_request_context,
        logger=logger,
        product_url=product_url,
        is_legacy_service=is_legacy_service,
    )
    assert is_service_ready, "the service failed starting!"


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
            msg=(
                f"pipeline is in {current_state=}, waiting for one of {expected_states=}",
                f"pipeline is now in {current_state=}",
            ),
        ):
            waiter = SocketIOProjectStateUpdatedWaiter(
                expected_states=expected_states + _FAIL_FAST_COMPUTATIONAL_STATES
            )
            with websocket.expect_event(
                "framereceived", waiter, timeout=timeout_ms
            ) as event:
                current_state = retrieve_project_state_from_decoded_message(
                    decode_socketio_42_message(event.value)
                )
            if (
                current_state in _FAIL_FAST_COMPUTATIONAL_STATES
                and current_state not in expected_states
            ):
                pytest.fail(
                    f"Pipeline failed with state {current_state}. Expected one of {expected_states}"
                )
    return current_state


def _node_started_predicate(request: Request) -> bool:
    return bool(
        re.search(NODE_START_REQUEST_PATTERN, request.url)
        and request.method.upper() == "POST"
    )


def _trigger_service_start(page: Page, node_id: str) -> None:
    with (
        log_context(logging.INFO, msg="trigger start button"),
        page.expect_request(_node_started_predicate, timeout=35 * SECOND),
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
    websocket: RobustWebSocket,
    timeout: int,
    press_start_button: bool,
    product_url: AnyUrl,
    is_service_legacy: bool,
    assertion_output_folder: Path,
) -> Generator[ServiceRunning, None, None]:
    with log_context(
        logging.INFO, msg=f"Waiting for node to run. Timeout: {timeout}"
    ) as ctx:
        waiter = SocketIONodeProgressCompleteWaiter(
            node_id=node_id,
            logger=ctx.logger,
            product_url=product_url,
            api_request_context=page.request,
            is_service_legacy=is_service_legacy,
            assertion_output_folder=assertion_output_folder,
        )
        service_running = ServiceRunning(iframe_locator=None)

        with websocket.expect_event("framereceived", waiter, timeout=timeout):
            if press_start_button:
                _trigger_service_start(page, node_id)

            yield service_running
        wait_for_service_ready(
            node_id,
            api_request_context=page.request,
            logger=ctx.logger,
            product_url=product_url,
            is_legacy_service=is_service_legacy,
        )
    service_running.iframe_locator = page.frame_locator(
        f'[osparc-test-id="iframe_{node_id}"]'
    )


def wait_for_service_running(
    *,
    page: Page,
    node_id: str,
    websocket: RobustWebSocket,
    timeout: int,
    press_start_button: bool,
    product_url: AnyUrl,
    is_service_legacy: bool,
    assertion_output_folder: Path,
) -> FrameLocator:
    """NOTE: if the service was already started this will not work as some of the required websocket events will not be emitted again
    In which case this will need further adjutment"""

    with log_context(
        logging.INFO, msg=f"Waiting for node to run. Timeout: {timeout}"
    ) as ctx:
        waiter = SocketIONodeProgressCompleteWaiter(
            node_id=node_id,
            logger=ctx.logger,
            product_url=product_url,
            api_request_context=page.request,
            is_service_legacy=is_service_legacy,
            assertion_output_folder=assertion_output_folder,
        )
        with websocket.expect_event("framereceived", waiter, timeout=timeout):
            if press_start_button:
                _trigger_service_start(page, node_id)

        wait_for_service_ready(
            node_id,
            api_request_context=page.request,
            logger=ctx.logger,
            product_url=product_url,
            is_legacy_service=is_service_legacy,
        )
    return page.frame_locator(f'[osparc-test-id="iframe_{node_id}"]')


def app_mode_trigger_next_app(page: Page) -> None:
    with (
        log_context(logging.INFO, msg="triggering next app"),
        page.expect_request(_node_started_predicate),
    ):
        # Move to next step (this auto starts the next service)
        page.get_by_test_id("AppMode_NextBtn").click()


def wait_for_label_text(
    page: Page, locator: str, substring: str, timeout: int = 10000
) -> Locator:
    page.locator(locator).wait_for(state="visible", timeout=timeout)

    page.wait_for_function(
        f"() => document.querySelector('{locator}').innerText.includes('{substring}')",
        timeout=timeout,
    )

    return page.locator(locator)
