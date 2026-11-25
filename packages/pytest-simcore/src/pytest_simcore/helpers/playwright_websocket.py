# pylint:disable=too-many-instance-attributes
"""Robust websocket handling and socket.io message decoding for the e2e tests."""

import asyncio
import contextlib
import json
import logging
import threading
import time
import typing
import weakref
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import TracebackType
from typing import Any, Final

from models_library.projects_state import ProjectStatus, RunningState
from models_library.rabbitmq_messages import ProgressType
from playwright._impl._sync_base import EventContextManager, EventInfo
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import (
    Page,
    WebSocket,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from .logging_tools import ContextMessages, log_context
from .playwright_constants import SECOND

_logger = logging.getLogger(__name__)


class _OSparcMessages(StrEnum):
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

_WEBSOCKET_CREATION_WAIT_SLICE: Final[int] = 3 * SECOND

_TRACKED_WEBSOCKETS: weakref.WeakKeyDictionary[Page, list[_TrackedWebSocket]] = weakref.WeakKeyDictionary()


@dataclass(slots=True)
class _TrackedWebSocket:
    socket: WebSocket
    frames_received: bool = False


def start_websocket_tracking(page: Page) -> None:
    """Records every websocket ``page`` creates from now on, including the ones its frames create.

    ``page.expect_websocket`` resolves for sockets created *after* it is entered, so a connection
    that the browser's socket.io client re-establishes on its own stays invisible to a waiter that
    started later. Recording the sockets here lets `RobustWebSocket` adopt an already connected
    socket instead of waiting for an event that was delivered before it started listening.

    Calling this again on the same page does nothing. Tracking must therefore start as early as the
    page exists.
    """
    if page in _TRACKED_WEBSOCKETS:
        return

    tracked: list[_TrackedWebSocket] = []
    _TRACKED_WEBSOCKETS[page] = tracked

    def on_websocket(socket: WebSocket) -> None:
        entry = _TrackedWebSocket(socket=socket)
        tracked.append(entry)
        # NOTE: a received frame proves the handshake completed, which the socket's mere existence
        # does not: a socket.io connection refused by a cold-starting service still creates one.
        socket.on("framereceived", lambda _: setattr(entry, "frames_received", True))

    page.on("websocket", on_websocket)

    # NOTE: `RobustWebSocket` listeners on a tracked socket reference the page back, and the registry
    # references the socket, so the weak key alone would keep the whole chain alive after a test ends.
    # Forgetting the page on close drops the strong side of that cycle.
    def _forget(_page: Page) -> None:
        _TRACKED_WEBSOCKETS.pop(page, None)

    page.on("close", _forget)


def _websocket_endpoint(socket: WebSocket) -> str:
    """The websocket URL without its query, which socket.io fills with per-attempt parameters."""
    return socket.url.split("?", maxsplit=1)[0]


def _tracked_entries_newest_first(page: Page, stop_at: WebSocket | None = None) -> list[_TrackedWebSocket]:
    """The sockets recorded for ``page``, newest first, stopping before ``stop_at``.

    A reconnection is recorded after the socket it replaces, so scanning past ``stop_at`` could
    only reach sockets that predate it: stale halves of its own session, or an independent session
    whose events this waiter must not consume.
    """
    tracked = _TRACKED_WEBSOCKETS.get(page, ())
    for index, entry in enumerate(reversed(tracked)):
        if entry.socket is stop_at:
            return list(reversed(tracked[len(tracked) - index :]))
    return list(reversed(tracked))


def _find_live_websocket(
    page: Page, *, exclude: WebSocket | None = None, ws_predicate: typing.Callable[[WebSocket], bool] | None = None
) -> WebSocket | None:
    """Returns the most recently created socket of ``page`` that is open and proved its handshake.

    A socket is adopted only after it received a frame: Playwright emits its ``websocket`` event when
    the request is sent, before the handshake completes, so a frameless socket may still be connecting
    or have failed. The engine.io protocol answers an accepted connection with an ``open`` packet, so a
    connected socket.io socket receives a frame shortly after the upgrade.
    Searching newest first, and not past ``exclude``: a reconnection is always recorded after the socket
    it replaces.
    Without ``ws_predicate``, only a socket on the same endpoint as ``exclude`` qualifies, so that an
    unrelated connection is never mistaken for the reconnection of another one.
    Returns None when the page is not tracked or no socket qualifies.
    """
    for entry in _tracked_entries_newest_first(page, stop_at=exclude):
        socket = entry.socket
        if socket is exclude or not entry.frames_received or socket.is_closed():
            continue
        if ws_predicate is not None:
            if not ws_predicate(socket):
                continue
        elif exclude is not None and _websocket_endpoint(socket) != _websocket_endpoint(exclude):
            continue
        return socket
    return None


@dataclass(eq=False)  # identity-hashed: instances are held in a `WeakSet`
class _ReconnectableEventWaiter:
    """Wraps `WebSocket.expect_event()` so a pending wait survives `RobustWebSocket`
    reconnections instead of raising a stale ``Socket closed`` error.

    `RobustWebSocket` calls `reattach_on_reconnection` on the waiters it registered when it
    adopts a socket, which keeps the wait listening before the caller gets a chance to send
    anything on the new connection.
    """

    robust_websocket: RobustWebSocket
    event: str
    predicate: typing.Callable | None
    timeout: float | None

    _deadline: datetime | None = field(init=False, default=None)
    _reattach_attempts: int = field(init=False, default=0)
    _failed_reattachment: PlaywrightError | None = field(init=False, default=None)
    _closed: bool = field(init=False, default=False)

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
        try:
            if exc_val is not None:
                if self._ctx is not None:
                    self._ctx.__exit__(exc_type, exc_val, exc_tb)
            elif (is_done := getattr(self.predicate, "is_done", None)) is not None and is_done():
                # The predicate saw its event but could not report it as a match at the time (e.g. its
                # project uuid was still unknown): cancel the pending wait.
                if self._ctx is not None:
                    self._ctx.__exit__(PlaywrightError, PlaywrightError("wait already satisfied"), None)
            else:
                _ = self.value
        finally:
            # only closed once the wait is over: a reconnection happening while `.value` above is
            # still blocked must move the wait to the new socket
            self._closed = True

    @property
    def value(self) -> typing.Any:
        """returns the same value as `EventInfo.value` making the result of `socket.expect_event` behave similarly"""

        while True:
            if self._failed_reattachment is not None:
                raise self._failed_reattachment
            assert self._event_info is not None  # nosec
            event_info = self._event_info
            try:
                return event_info.value
            except (PlaywrightError, asyncio.CancelledError) as exc:
                if self._failed_reattachment is not None:
                    # a move attempt failed, which is also what cancelled this pending read on the
                    # old socket: report why moving the wait failed, not the stale error raised by
                    # the connection that died
                    raise self._failed_reattachment from exc
                if self._event_info is not event_info:
                    # a reconnection moved this wait to another connection while the read above was
                    # blocked on the socket that died (moving it cancels this pending event), so read
                    # the pending event of the connection that replaced it
                    continue
                if _SOCKET_CLOSED_ERROR_MESSAGE not in f"{exc}" or self.robust_websocket.ws is self._bound_ws:
                    raise

                self._enforce_reattach_limit(exc)
                with log_context(
                    logging.INFO,
                    msg=f"Reattaching wait for {self.event!r} to newly reconnected websocket",
                ):
                    self._attach()

    def reattach_on_reconnection(self) -> None:
        """Moves a pending wait to the websocket `RobustWebSocket` just adopted.

        `expect_event` only reports the frames that arrive after it is attached, so leaving the
        wait on the dead socket until `.value` raises `Socket closed` loses whatever the new
        connection delivered in the meantime.
        """
        if self._closed or self._ctx is None or self._bound_ws is self.robust_websocket.ws:
            return
        if self._event_info is not None and self._event_info.is_done():
            try:
                # The frame landed before the connection changed: re-arming would cancel the
                # pending read and throw its value away. A settled event is read without waiting.
                _ = self._event_info.value
            except (PlaywrightError, asyncio.CancelledError) as exc:
                if not isinstance(exc, asyncio.CancelledError) and _SOCKET_CLOSED_ERROR_MESSAGE not in f"{exc}":
                    # The wait settled with its own error (e.g. Playwright's per-call timeout): that
                    # is the error the caller must read, and re-arming would restart an expired wait
                    return
                # The pending event was rejected instead (closing the socket rejects everything it
                # was still waiting for), so this wait is pending on a connection that is gone
            else:
                return
        with log_context(logging.INFO, msg=f"Moving wait for {self.event!r} to the reconnected websocket") as ctx:
            try:
                # moving a wait is a reattachment like the one `.value` does when it notices the
                # socket was replaced, so it counts against the same limit
                self._enforce_reattach_limit(None)
                self._attach()
            except PlaywrightError as exc:  # the deadline may have expired while disconnected
                self._failed_reattachment = exc
                ctx.logger.warning("could not move the wait for %s: %s", self.event, exc)
            else:
                self._failed_reattachment = None

    def _enforce_reattach_limit(self, exc: BaseException | None) -> None:
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

        ctx = self._bound_ws.expect_event(self.event, self.predicate, timeout=remaining_timeout)
        self._ctx = ctx
        self._event_info = ctx.__enter__()


@dataclass
class RobustWebSocket:
    page: Page
    ws: WebSocket
    _num_reconnections: int = 0
    auto_reconnect: bool = True
    ws_predicate: typing.Callable[[WebSocket], bool] | None = None
    reconnect_timeout: float = 5 * SECOND
    log_prefix: str = _WEBSOCKET_MESSAGE_PREFIX
    _reconnect_lock: threading.Lock = field(init=False, repr=False, default_factory=threading.Lock)
    _reconnect_handled: set[int] = field(init=False, repr=False, default_factory=set)
    _frames_received_on: set[int] = field(init=False, repr=False, default_factory=set)
    _adopted_unproven: set[int] = field(init=False, repr=False, default_factory=set)
    # waits still in flight, dropped as soon as the caller releases them
    _pending_event_waiters: weakref.WeakSet[_ReconnectableEventWaiter] = field(
        init=False, repr=False, default_factory=weakref.WeakSet
    )

    def __post_init__(self) -> None:
        start_websocket_tracking(self.page)
        self._configure_websocket_events()
        if self.ws.is_closed():
            if not self.auto_reconnect:
                return
            # NOTE: a websocket whose handshake already failed (e.g. a socket.io connection refused
            # during a service's cold start) has already fired its events before being captured,
            # so the listeners attached above never see them: reconnect right away.
            _logger.warning("%s WebSocket is already closed. Attempting to reconnect...", self.log_prefix)
            self._reconnect_handled.add(id(self.ws))
            self._attempt_reconnect(_logger)
        else:
            # NOTE: a socket that is not closed completed its handshake: it is connected even if its
            # first frame (e.g. the socket.io 'open' packet) was already delivered before the
            # listeners above could be attached, since `page.expect_websocket` resolves as soon as
            # the browser *creates* the socket. Without this, `wait_until_connected` would wait for
            # an unrelated later frame (engine.io pings come ~25s later) on a healthy socket.
            self._mark_connected(self.ws)

    def _mark_connected(self, socket: WebSocket) -> None:
        self._frames_received_on.add(id(socket))

    def _drop_unproven_reconnection(self, socket: WebSocket, logger: logging.Logger) -> None:
        """Un-counts an adopted socket that died before receiving any frame.

        A socket adopted by `_attempt_reconnect` can still fail its handshake, since
        `page.expect_websocket` resolves as soon as the browser creates it. Its first frame is what
        tells a reconnection apart from such a failed attempt, so the count is only kept once it
        arrives.
        """
        if id(socket) not in self._adopted_unproven:
            return
        self._adopted_unproven.discard(id(socket))
        self._num_reconnections = max(0, self._num_reconnections - 1)
        logger.info(
            "%s❌ Dropped WebSocket adopted while reconnecting. Number of reconnections: %s",
            self.log_prefix,
            self._num_reconnections,
        )

    def _configure_websocket_events(self) -> None:
        # NOTE: bind the current socket in the closure: the 'socketerror' event only carries the
        # error message, so the socket must be identified through the closure instead.
        socket = self.ws

        with log_context(
            logging.INFO,
            msg="handle websocket message (set to --log-cli-level=DEBUG level if you wanna see all of them)",
        ) as ctx:

            def on_framesent(payload: str | bytes) -> None:
                ctx.logger.debug("%s⬇️ Frame sent: %s", self.log_prefix, payload)

            def on_framereceived(payload: str | bytes) -> None:
                # NOTE: receiving a frame is the proof that this socket's handshake succeeded
                # (a socket.io server sends its 'open' packet immediately on connect)
                self._frames_received_on.add(id(socket))
                self._adopted_unproven.discard(id(socket))
                ctx.logger.debug("%s⬆️ Frame received: %s", self.log_prefix, payload)

            def _trigger_reconnect(reason: str) -> None:
                with self._reconnect_lock:
                    # NOTE: a failed handshake emits both 'socketerror' and 'close' on the same
                    # socket; only the first event may trigger a reconnect, the second wait would
                    # otherwise hang until timeout waiting for a websocket that never arrives.
                    if id(socket) in self._reconnect_handled:
                        return
                    self._reconnect_handled.add(id(socket))
                ctx.logger.warning("%s⚠️ %s. Attempting to reconnect...", self.log_prefix, reason)
                self._attempt_reconnect(ctx.logger)

            def on_close(_: WebSocket) -> None:
                # NOTE: a closed socket is no longer proof of connectivity: without dropping
                # the stale proof, `wait_until_connected` would return immediately on the
                # dead socket while its (event-dispatched) reconnection has not completed yet.
                self._frames_received_on.discard(id(socket))
                self._drop_unproven_reconnection(socket, ctx.logger)
                if not self.auto_reconnect:
                    ctx.logger.info("%s WebSocket closed.", self.log_prefix)
                    return
                _trigger_reconnect("WebSocket closed")

            def on_socketerror(error_msg: str) -> None:
                self._frames_received_on.discard(id(socket))
                self._drop_unproven_reconnection(socket, ctx.logger)
                if not self.auto_reconnect:
                    ctx.logger.error("%s❌ WebSocket error: %s", self.log_prefix, error_msg)
                    return
                # NOTE: expected during e.g. a service cold start, where the socket.io client
                # immediately retries (polling, then websocket upgrade).
                ctx.logger.warning("%s❌ WebSocket error: %s (expecting a reconnection)", self.log_prefix, error_msg)
                _trigger_reconnect(f"WebSocket error: {error_msg}")

            # Attach core event listeners
            socket.on("framesent", on_framesent)
            socket.on("framereceived", on_framereceived)
            socket.on("close", on_close)
            socket.on("socketerror", on_socketerror)

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

        def _accept(new_websocket: WebSocket) -> bool:
            if new_websocket.is_closed():
                return False
            if self.ws_predicate is not None:
                return self.ws_predicate(new_websocket)
            # a reconnection replaces the socket it reconnects: same endpoint, as in
            # `_find_live_websocket`, so that an unrelated connection is never adopted
            return _websocket_endpoint(new_websocket) == _websocket_endpoint(self.ws)

        already_connected = _find_live_websocket(self.page, exclude=self.ws, ws_predicate=self.ws_predicate)
        if already_connected is not None:
            # NOTE: the socket.io client may have finished reconnecting before this wait started;
            # adopt it instead of waiting for a `websocket` event that was already delivered
            self._use_websocket(already_connected, logger, source="already connected")
            return

        # NOTE: `expect_websocket` only resolves for sockets created after it is entered, so a socket
        # created just before this loop -- or during one of its slices -- can never satisfy it: its
        # handshake may complete while the slice is running, and no further creation event follows.
        # Waiting in slices and re-checking the registry between them bounds that stall to one slice.
        deadline = time.monotonic() + self.reconnect_timeout / SECOND
        while True:
            remaining = (deadline - time.monotonic()) * SECOND
            if remaining <= 0:
                msg = (
                    f"Timeout {self.reconnect_timeout}ms exceeded while waiting for a websocket "
                    f"on {self.ws.url} to reconnect."
                )
                raise PlaywrightTimeoutError(msg)
            try:
                with self.page.expect_websocket(
                    _accept, timeout=min(_WEBSOCKET_CREATION_WAIT_SLICE, remaining)
                ) as ws_info:
                    assert not ws_info.value.is_closed()
            except PlaywrightTimeoutError:
                if reconnecting := _find_live_websocket(self.page, exclude=self.ws, ws_predicate=self.ws_predicate):
                    self._use_websocket(reconnecting, logger, source="already connected")
                    return
            else:
                self._use_websocket(ws_info.value, logger, source="reconnected")
                return

    def _use_websocket(self, socket: WebSocket, logger: logging.Logger, *, source: str) -> None:
        """Switches to ``socket`` and re-attaches the event listeners to it."""
        self.ws = socket
        self._num_reconnections += 1
        # NOTE: `_accept` guaranteed this socket's handshake completed, so it is connected even if
        # its first frame raced ahead of the listeners attached below (same as in __post_init__).
        # The browser also creates a websocket for a connection attempt whose handshake then fails
        # (the socket.io client retries on its own while offline), so this socket must still receive
        # a frame before its reconnection counts: see `_drop_unproven_reconnection`.
        self._adopted_unproven.add(id(self.ws))
        self._mark_connected(self.ws)
        logger.info(
            "🔄 WebSocket %s successfully (%s). Number of reconnections: %s",
            source,
            self.ws.url,
            self._num_reconnections,
        )
        self._configure_websocket_events()
        # NOTE: a wait left on the socket that just died cannot see what this connection delivers,
        # so it is moved here instead of when the caller happens to read it. A moved wait starts at
        # the frames this connection receives from now on, which includes whatever a protocol
        # handshake still sends on it: a caller that must not mistake one of those for its answer
        # filters them with a predicate.
        self._reattach_pending_event_waiters()

    def _reattach_pending_event_waiters(self) -> None:
        """Moves the waits left on the socket this one replaced onto this socket."""
        for waiter in list(self._pending_event_waiters):
            try:
                waiter.reattach_on_reconnection()
            except Exception:  # nosec  # pylint: disable=broad-except
                # one wait that cannot be moved must not abort the reconnection of all the others
                _logger.exception(
                    "%sCould not move the wait for %s to the reconnected websocket",
                    self.log_prefix,
                    waiter.event,
                )

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
        waiter = _ReconnectableEventWaiter(robust_websocket=self, event=event, predicate=predicate, timeout=timeout)
        self._pending_event_waiters.add(waiter)
        return waiter

    def expect_project_closed(self, project_uuid: str, *, timeout: timedelta) -> _ReconnectableEventWaiter:
        """Register a listener that waits until `project_uuid` is closed (and unlocked)"""
        return self.expect_event(
            "framereceived",
            SocketIOProjectClosedWaiter(project_uuid=project_uuid),
            timeout=timeout.total_seconds() * SECOND,
        )

    def wait_until_connected(self, *, timeout: float) -> None:
        """
        Block until the current websocket is connected, i.e. it received its first frame
        (possibly after a reconnection), raising a `TimeoutError` if that does not happen
        within `timeout` milliseconds.
        """
        with log_context(logging.INFO, msg=f"waiting for websocket connection (timeout: {timeout}ms)") as ctx:
            deadline = datetime.now(UTC) + timedelta(milliseconds=timeout)
            while True:
                # NOTE: pumping the page's event loop lets event-driven reconnections proceed.
                # It must happen *before* evaluating connectivity: websocket events are
                # dispatched only while the loop is pumped, so a 'close' that the browser has
                # already emitted but that has not been dispatched yet would otherwise leave a
                # stale proof-of-life on the (now dead) socket and make this return immediately.
                self.page.wait_for_timeout(100)
                if not self.ws.is_closed() and id(self.ws) in self._frames_received_on:
                    break
                if datetime.now(UTC) > deadline:
                    msg = f"Timeout {timeout}ms exceeded while waiting for the websocket to connect."
                    raise PlaywrightTimeoutError(msg)
            ctx.logger.debug("%s WebSocket is connected.", self.log_prefix)


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
    progress_type: ProgressType
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
        progress_type=ProgressType(event.obj["progress_type"]),
        current_progress=float(event.obj["progress_report"]["actual_value"]),
        total_progress=float(event.obj["progress_report"]["total"]),
    )


@dataclass
class SocketIOProjectClosedWaiter:
    """Waits for `project_uuid` to close, ignoring the closing of other projects"""

    project_uuid: str

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if (
                    (decoded_message.name == _OSparcMessages.PROJECT_STATE_UPDATED.value)
                    and (retrieve_project_id_from_decoded_message(decoded_message) == self.project_uuid)
                    and (decoded_message.obj["data"]["shareState"]["status"] == ProjectStatus.CLOSED)
                    and (decoded_message.obj["data"]["shareState"]["locked"] is False)
                ):
                    ctx.logger.info("project %s successfully closed", self.project_uuid)
                    return True

        return False


@dataclass
class SocketIOProjectStateUpdatedWaiter:
    """Waits for `project_uuid` to reach one of `expected_states`, ignoring other projects"""

    expected_states: tuple[RunningState, ...]
    # None for as long as the caller has not learned the uuid yet, see `is_done`
    project_uuid: str | None

    # every (uuid, state) seen so far, since a frame received while `project_uuid` was still
    # unknown may well be the awaited update and will not be sent again
    _seen_states: list[tuple[str, RunningState]] = field(init=False, default_factory=list, repr=False)

    def __call__(self, message: str) -> bool:
        with log_context(logging.DEBUG, msg=f"handling websocket {message=}") as ctx:
            # socket.io encodes messages like so
            # https://stackoverflow.com/questions/24564877/what-do-these-numbers-mean-in-socket-io-payload
            if message.startswith(SOCKETIO_MESSAGE_PREFIX):
                decoded_message = decode_socketio_42_message(message)
                if decoded_message.name == _OSparcMessages.PROJECT_STATE_UPDATED.value:
                    event_project_uuid = retrieve_project_id_from_decoded_message(decoded_message)
                    event_state = retrieve_project_state_from_decoded_message(decoded_message)
                    self._seen_states.append((event_project_uuid, event_state))

                    if self.project_uuid is None:
                        ctx.logger.debug(
                            "remembering %s of project %s until the expected project uuid is known",
                            event_state,
                            event_project_uuid,
                        )
                        return False

                    if event_project_uuid != self.project_uuid:
                        # a different project (e.g. a previous test/job's project still open or
                        # closing on the shared user): ignore it and keep waiting for ours
                        ctx.logger.debug(
                            "ignoring projectStateUpdated for other project %s (waiting for %s)",
                            event_project_uuid,
                            self.project_uuid,
                        )
                        return False
                    return event_state in self.expected_states

            return False

    def is_done(self) -> bool:
        """Whether an earlier frame already met the expectation, e.g. one delivered while
        `project_uuid` was still unknown and hence unmatchable at the time"""
        return self.project_uuid is not None and any(
            event_project_uuid == self.project_uuid and event_state in self.expected_states
            for event_project_uuid, event_state in self._seen_states
        )

    def last_state_seen(self) -> RunningState | None:
        """The most recent state pushed for `project_uuid`, which can be further along than the
        state the wait started from: only the state that matches the expectation ends the wait"""
        if self.project_uuid is None:
            return None
        return next(
            (
                state
                for event_project_uuid, state in reversed(self._seen_states)
                if event_project_uuid == self.project_uuid
            ),
            None,
        )


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
    runs. Unlike checking the UI after the fact, this verifies the websocket push actually
    happened.
    """
    waiter = SocketIOWaitNodesForOutputs(node_id_to_expected_number_of_outputs=node_id_to_expected_number_of_outputs)
    # NOTE: the db-listener TIP describes a wait that ran out of time after the caller's block
    # finished. If that block raised, the pipeline never produced outputs and no push was ever
    # expected; if the websocket failed, the push was never listened for
    caller_block_completed = False
    outputs_wait_timed_out = False
    with log_context(
        logging.INFO,
        msg=ContextMessages(
            starting=f"⏳ waiting for outputs push for nodes {list(node_id_to_expected_number_of_outputs)}",
            done="✅ received outputs push for all expected nodes",
            raised=lambda: (
                f"❌ missing outputs push for: {waiter.missing_outputs_report()}. "
                + (
                    "TIP: check that the webserver's db-listener service is running properly!"
                    if caller_block_completed and outputs_wait_timed_out
                    else "("
                    "the outputs wait never timed out: the caller's block or the websocket failed first, "
                    "see its error above)"
                )
            ),
        ),
    ):
        try:
            with websocket.expect_event("framereceived", waiter, timeout=timeout):
                yield
                # NOTE: the wait only resolves when this context exits and reads the pending event,
                # so the block is already over by the time a timeout surfaces
                caller_block_completed = True
        except PlaywrightTimeoutError:
            outputs_wait_timed_out = True
            raise
