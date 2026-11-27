"""Waits for a dynamic service to start, attach its iframe and answer on its endpoint."""

import contextlib
import json
import logging
import re
from collections import defaultdict
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Final

import arrow
import pytest
from annotated_types import doc
from models_library.rabbitmq_messages import ProgressType
from playwright.sync_api import (
    APIRequestContext,
    FrameLocator,
    Page,
    Request,
)
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyUrl, TypeAdapter
from tenacity import (
    RetryError,
    Retrying,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_delay,
    wait_fixed,
)

from .logging_tools import log_context
from .playwright_constants import SECOND
from .playwright_websocket import (
    SOCKETIO_MESSAGE_PREFIX,
    RobustWebSocket,
    SocketIOEvent,
    _OSparcMessages,
    decode_socketio_42_message,
    retrieve_node_progress_from_decoded_message,
)

_logger = logging.getLogger(__name__)

NODE_START_REQUEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"/projects/[^/]+/nodes/[^:]+:start")

_APP_MODE_NEXT_APP_START_REQUEST_TIMEOUT: Final[int] = 5 * SECOND

# Progress types a starting dynamic service is expected to report before its start is complete
REQUIRED_PROGRESS_TYPES_FOR_STARTED_SERVICE: Final[frozenset[ProgressType]] = frozenset(
    {
        ProgressType.SERVICE_INPUTS_PULLING,
        ProgressType.SIDECARS_PULLING,
        ProgressType.SERVICE_OUTPUTS_PULLING,
        ProgressType.SERVICE_STATE_PULLING,
        ProgressType.SERVICE_IMAGES_PULLING,
        ProgressType.SERVICE_CONTAINERS_STARTING,
    }
)

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
        except PlaywrightTimeoutError, TimeoutError:
            logger.exception(
                "❌ Timed-out requesting service endpoint after %ds ❌",
                _SERVICE_ROOT_POINT_STATUS_TIMEOUT.total_seconds(),
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
    _current_progress: dict[ProgressType, float] = field(default_factory=defaultdict)
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
                                len(REQUIRED_PROGRESS_TYPES_FOR_STARTED_SERVICE),
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
            progress_type in self._current_progress for progress_type in REQUIRED_PROGRESS_TYPES_FOR_STARTED_SERVICE
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


_MIN_TIMEOUT_WAITING_FOR_SERVICE_ENDPOINT: Final[
    Annotated[timedelta, doc("floor left to the endpoint check after the start waits")]
] = timedelta(seconds=30)


def _service_iframe_selector(node_id: str) -> str:
    return f'[osparc-test-id="iframe_{node_id}"]'


def _service_iframe_locator(page: Page, node_id: str) -> FrameLocator:
    """Returns the service iframe for ``node_id``, resilient to duplicate iframes."""
    iframe_selector = _service_iframe_selector(node_id)
    iframe_count = page.locator(iframe_selector).count()
    if iframe_count > 1:
        _logger.warning(
            "Found %d iframes with duplicate osparc-test-id for node %s; using the first one "
            "(see ITISFoundation/osparc-simcore#9541)",
            iframe_count,
            node_id,
        )
    return page.frame_locator(iframe_selector).first


_SERVICE_IFRAME_NAVIGATION_TIMEOUT: Final[
    Annotated[
        timedelta,
        doc("grace given to the UI to navigate the service iframe itself before this helper forces it"),
    ]
] = timedelta(seconds=30)

_SERVICE_FRAME_ATTACH_TIMEOUT: Final[
    Annotated[timedelta, doc("grace window for the driver to attach an in-flight iframe navigation")]
] = timedelta(seconds=10)

_SERVICE_FRAME_POLL_INTERVAL: Final[timedelta] = timedelta(milliseconds=250)


def _service_frame_attached(page: Page, node_id: str) -> bool:
    """Whether the driver attached the content frame of the service iframe of ``node_id``.

    Only the frame URL carries the node id, so the stale frame left by the iframe's previous
    navigation (e.g. ``about:blank``) counts as unattached, and the first iframe of a duplicate
    pair is checked on its own instead of through any attached duplicate.
    Checking the iframe's ``src`` attribute is not an option: the UI navigates the service iframe
    through ``qx.bom.Iframe.setSource``, which calls ``location.replace`` on the content window and
    therefore never writes the attribute.
    A failed read returns False instead of raising.
    """
    try:
        # NOTE: unlike `Locator`, `query_selector` does not auto-wait, keeping each poll short
        iframe_element = page.query_selector(_service_iframe_selector(node_id))
        if iframe_element is None:
            return False
        content_frame = iframe_element.content_frame()
    except PlaywrightError:
        return False
    return content_frame is not None and node_id in content_frame.url


def _wait_service_frame_attached(page: Page, node_id: str, timeout: timedelta) -> bool:
    poller = Retrying(
        stop=stop_after_delay(timeout.total_seconds()),
        wait=wait_fixed(_SERVICE_FRAME_POLL_INTERVAL.total_seconds()),
        retry=retry_if_result(lambda attached: not attached),
        before_sleep=before_sleep_log(_logger, logging.DEBUG),
    )
    try:
        return bool(poller(lambda: _service_frame_attached(page, node_id)))
    except RetryError:
        return False


def _ensure_service_iframe_attached(page: Page, node_id: str, service_url: AnyUrl, *, is_legacy_service: bool) -> None:
    """Navigates the service iframe when the UI did not, or the driver never attached its frame.

    Firefox intermittently does not attach the content frame of a rendered
    cross-origin iframe (microsoft/playwright#43007), which makes every query on
    its ``FrameLocator`` hang until timeout even though the service UI is fully
    shown. Setting the iframe source navigates it and re-triggers the frame
    lifecycle events the driver needs to attach the content frame.

    The UI navigates the iframe on its own, shortly after its readiness polling
    has seen the service, so this waits for that navigation before forcing one:
    navigating an iframe that is already loading would restart it. The service
    endpoint has already replied at this point, so navigating to its URL here is
    a valid fallback for an iframe the UI left on ``about:blank``.

    Best-effort: failed reads while polling are retried, the iframe is
    navigated at most once, and Playwright errors are logged and swallowed,
    so that the caller still fails with its own original error.
    """
    try:
        if _wait_service_frame_attached(page, node_id, _SERVICE_IFRAME_NAVIGATION_TIMEOUT):
            return

        if is_legacy_service:
            # NOTE: a legacy service's iframe URL is its `service_basepath` plus the optional
            # `entry_point` (see `osparc.utils.Utils.computeServiceModelData` in the frontend), while
            # `service_url` here is only the `/x/<node_id>` path. Navigating would load a different
            # page than the UI intended, so leave the iframe alone and let the caller fail with its
            # own original error.
            _logger.warning(
                "Service iframe content frame of node %s did not attach within %s: not navigating it "
                "because its full URL is not known for a legacy service",
                node_id,
                _SERVICE_IFRAME_NAVIGATION_TIMEOUT,
            )
            return

        _logger.warning(
            "Service iframe content frame of node %s did not attach within %s: navigating it to %s",
            node_id,
            _SERVICE_IFRAME_NAVIGATION_TIMEOUT,
            service_url,
        )
        page.locator(_service_iframe_selector(node_id)).first.evaluate(
            "(element, url) => { element.src = url; }",
            f"{service_url}",
            timeout=int(_SERVICE_FRAME_ATTACH_TIMEOUT.total_seconds() * SECOND),
        )
        if _wait_service_frame_attached(page, node_id, _SERVICE_FRAME_ATTACH_TIMEOUT):
            _logger.info("Service iframe content frame of node %s attached after navigating it", node_id)
        else:
            _logger.warning(
                "Service iframe content frame of node %s is still not attached after navigating it to %s",
                node_id,
                service_url,
            )
    except PlaywrightError:
        _logger.exception(
            "Could not ensure the service iframe content frame of node %s is attached; "
            "continuing so that the caller reports its own original error",
            node_id,
        )


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
            int(_MIN_TIMEOUT_WAITING_FOR_SERVICE_ENDPOINT.total_seconds() * SECOND),
        ),
    )
    _ensure_service_iframe_attached(
        page,
        node_id,
        _get_service_url(node_id, product_url, is_legacy_service=is_service_legacy),
        is_legacy_service=is_service_legacy,
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
            int(_MIN_TIMEOUT_WAITING_FOR_SERVICE_ENDPOINT.total_seconds() * SECOND),
        ),
    )

    _ensure_service_iframe_attached(
        page,
        node_id,
        _get_service_url(node_id, product_url, is_legacy_service=is_service_legacy),
        is_legacy_service=is_service_legacy,
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
        except PlaywrightTimeoutError, TimeoutError:
            ctx.logger.exception(
                "❌ no start request detected within %s ms: the next service was likely already started ❌",
                _APP_MODE_NEXT_APP_START_REQUEST_TIMEOUT,
            )
