# pylint: disable=protected-access

import json
from collections import defaultdict
from collections.abc import Callable
from datetime import timedelta
from types import SimpleNamespace, TracebackType
from typing import Any, Final, Self, cast
from unittest import mock

import pytest
from models_library.projects_state import ProjectStatus, RunningState
from models_library.rabbitmq_messages import ProgressType
from playwright.sync_api import ElementHandle, Frame, Locator, Page, WebSocket
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import AnyUrl, TypeAdapter
from pytest_simcore.helpers import playwright as playwright_helpers
from pytest_simcore.helpers.playwright import (
    REQUIRED_PROGRESS_TYPES_FOR_STARTED_SERVICE,
    SOCKETIO_MESSAGE_PREFIX,
    RobustWebSocket,
    SocketIONodeProgressCompleteWaiter,
    SocketIOProjectClosedWaiter,
    SocketIOProjectStateUpdatedWaiter,
    _ensure_service_iframe_attached,
    _ReconnectableEventWaiter,
    start_websocket_tracking,
)

_NODE_ID: Final[str] = "d00cb7e0-8b78-4d5c-9b57-2a1f6c6a1234"


def _socketio_message(name: str, obj: dict[str, Any]) -> str:
    return f"{SOCKETIO_MESSAGE_PREFIX}{json.dumps([name, obj])}"


def _service_status_message(node_id: str, service_state: str) -> str:
    return _socketio_message("serviceStatus", {"service_uuid": node_id, "service_state": service_state})


def _node_progress_message(node_id: str, progress_type: ProgressType, ratio: float) -> str:
    return _socketio_message(
        "nodeProgress",
        {
            "node_id": node_id,
            "progress_type": progress_type.value,
            "progress_report": {"actual_value": ratio, "total": 1.0},
        },
    )


def _project_state_updated_message(project_uuid: str, running_state: RunningState) -> str:
    return _socketio_message(
        "projectStateUpdated",
        {
            "project_uuid": project_uuid,
            "data": {
                "state": {
                    "value": running_state.value,
                }
            },
        },
    )


def _project_share_state_message(project_uuid: str, *, status: ProjectStatus, locked: bool) -> str:
    return _socketio_message(
        "projectStateUpdated",
        {
            "project_uuid": project_uuid,
            "data": {
                "state": {"value": RunningState.SUCCESS.value},
                "shareState": {"status": status, "locked": locked},
            },
        },
    )


def test_idle_state_within_grace_period_does_not_fail_fast():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert done is False
    assert waiter.success is False


def test_idle_state_after_grace_period_fails_fast():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID, min_idle_before_fail_fast=timedelta(seconds=0))

    done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert done is True
    assert waiter.success is False


def test_idle_state_grace_period_is_anchored_on_first_status_message():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    # first idle message: well within the grace period
    first_done = waiter(_service_status_message(_NODE_ID, "idle"))
    assert first_done is False
    assert waiter.success is False

    # simulate that the node has been idle since well before the grace period,
    # without resetting the timer on this second message
    assert waiter._first_service_status_received_at is not None  # noqa: SLF001
    waiter._first_service_status_received_at -= timedelta(seconds=20)  # noqa: SLF001

    second_done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert second_done is True
    assert waiter.success is False


def test_idle_within_grace_period_still_triggers_stale_progress_fallback():
    """An idle status within its idle grace period must not bypass the stale-progress fallback.

    Regression test: otherwise the waiter could wait forever if the backend
    keeps reporting "idle" but never emits any nodeProgress message.
    """
    waiter = SocketIONodeProgressCompleteWaiter(
        node_id=_NODE_ID,
        max_idle_timeout=timedelta(seconds=0),
        min_idle_before_fail_fast=timedelta(hours=1),
    )

    done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert done is True
    assert waiter.success is True


def test_failed_state_fails_fast_immediately():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    done = waiter(_service_status_message(_NODE_ID, "failed"))

    assert done is True
    assert waiter.success is False


def test_node_progress_reaching_completion_marks_success():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    required_types = sorted(REQUIRED_PROGRESS_TYPES_FOR_STARTED_SERVICE, key=lambda t: t.value)
    done = False
    for progress_type in required_types:
        done = waiter(_node_progress_message(_NODE_ID, progress_type, 1.0))

    assert done is True
    assert waiter.success is True


_SERVICE_FRAME_URL: Final[str] = f"https://{_NODE_ID}.services.example.org/lab"
_SERVICE_URL: Final[AnyUrl] = TypeAdapter(AnyUrl).validate_python(f"https://{_NODE_ID}.services.example.org")


def _frame(url: str) -> Frame:
    frame = mock.create_autospec(Frame, instance=True)
    frame.url = url
    return frame


def _page_with_service_iframe(
    *,
    iframe_content: Frame | None,
    iframe_element_missing: bool = False,
    query_selector_error: Exception | None = None,
    evaluate_error: Exception | None = None,
    service_frame_visible: bool = False,
) -> tuple[Page, mock.Mock]:
    """Autospecced `Page` whose service iframe element attaches ``iframe_content``.

    Returns the page and the `Locator` the helper uses to navigate the iframe, so that tests can
    observe the fallback navigation. With ``service_frame_visible``, an attached duplicate frame is
    visible through ``page.frames`` only, never on the first iframe element.
    """
    page = mock.create_autospec(Page, instance=True)
    iframe_locator = mock.create_autospec(Locator, instance=True)
    iframe_element = mock.create_autospec(ElementHandle, instance=True)

    iframe_locator.first = iframe_locator
    iframe_element.content_frame.return_value = iframe_content
    if query_selector_error is not None:
        page.query_selector.side_effect = query_selector_error
    else:
        page.query_selector.return_value = None if iframe_element_missing else iframe_element
    if evaluate_error is not None:
        iframe_locator.evaluate.side_effect = evaluate_error
    # NOTE: the UI navigates service iframes with `location.replace`, so this always answers "no"
    page.evaluate.return_value = False
    page.frames = [_frame(_SERVICE_FRAME_URL)] if service_frame_visible else []
    page.locator.return_value = iframe_locator
    return page, iframe_locator


@pytest.fixture()
def _no_service_iframe_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the waiting windows of `_ensure_service_iframe_attached`."""
    monkeypatch.setattr(playwright_helpers, "_SERVICE_IFRAME_NAVIGATION_TIMEOUT", timedelta(0))
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_ATTACH_TIMEOUT", timedelta(0))
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_POLL_INTERVAL", timedelta(0))


def _navigated_url(iframe_locator: mock.Mock) -> str:
    assert iframe_locator.evaluate.call_count == 1
    expression, url = iframe_locator.evaluate.call_args.args
    assert "element.src = url" in expression
    return url


def test_healthy_service_iframe_is_left_untouched():
    page, iframe_locator = _page_with_service_iframe(iframe_content=_frame(_SERVICE_FRAME_URL))

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)

    iframe_locator.evaluate.assert_not_called()


def test_service_iframe_navigated_by_location_replace_is_not_re_navigated(_no_service_iframe_waits: None):
    """Regression test for the master e2e failures.

    The UI navigates the service iframe through `qx.bom.Iframe.setSource`, which calls
    `location.replace` on the content window and therefore never writes the `src` attribute.
    Probing that attribute made every service start wait out the whole timeout and then leave the
    iframe untouched, although its content frame was attached and showing the service.
    """
    page, iframe_locator = _page_with_service_iframe(iframe_content=_frame(_SERVICE_FRAME_URL))

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)

    cast("mock.Mock", page).evaluate.assert_not_called()
    iframe_locator.evaluate.assert_not_called()


def test_unattached_service_iframe_is_navigated_to_the_service(_no_service_iframe_waits: None):
    """Regression test for microsoft/playwright#43007.

    The service UI is rendered but its content frame never attaches, so the driver keeps exposing
    the stale frame of the previous navigation and queries hang forever. Re-setting the `src` to the
    service URL is what recovers it; re-reading the current one would navigate nowhere.
    """
    page, iframe_locator = _page_with_service_iframe(iframe_content=_frame("about:blank"))

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)

    assert _navigated_url(iframe_locator) == f"{_SERVICE_URL}"


def test_unattached_first_service_iframe_is_navigated_despite_attached_duplicate(_no_service_iframe_waits: None):
    """An attached duplicate must not mask the unattached first iframe.

    Regression test: with duplicate service iframes, the first one is what the returned
    `FrameLocator` queries.
    """
    page, iframe_locator = _page_with_service_iframe(iframe_content=None, service_frame_visible=True)

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)

    assert _navigated_url(iframe_locator) == f"{_SERVICE_URL}"


def test_service_iframe_not_rendered_yet_gets_the_navigation_attempted(_no_service_iframe_waits: None):
    """The iframe element may still be missing when the wait ends; navigating it must then wait
    for it instead of giving up, since the UI renders it while the service is being attached.
    """
    page, iframe_locator = _page_with_service_iframe(iframe_content=None, iframe_element_missing=True)

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)

    assert _navigated_url(iframe_locator) == f"{_SERVICE_URL}"


def _read_fails_then_returns(error: Exception, element: ElementHandle) -> Callable[[str], ElementHandle]:
    """Fails the first reads of the iframe element, as a busy page does, then serves ``element``."""
    remaining_failures = 2

    def read(_selector: str) -> ElementHandle:
        nonlocal remaining_failures
        if remaining_failures > 0:
            remaining_failures -= 1
            raise error
        return element

    return read


def test_transient_errors_during_polling_still_run_the_recovery(
    _no_service_iframe_waits: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """Transient Playwright errors while polling must not abort the helper.

    The polls run while the page is busy; a failed read counts as not yet attached and the next
    poll retries it, so the recovery still runs instead of an error escaping to the caller.
    """
    page, iframe_locator = _page_with_service_iframe(iframe_content=None)
    mock_page = cast("mock.Mock", page)
    monkeypatch.setattr(playwright_helpers, "_SERVICE_IFRAME_NAVIGATION_TIMEOUT", timedelta(seconds=1))
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_POLL_INTERVAL", timedelta(0))
    stale_element = mock.create_autospec(ElementHandle, instance=True)
    stale_element.content_frame.return_value = _frame("about:blank")
    mock_page.query_selector.side_effect = _read_fails_then_returns(
        PlaywrightError("Execution context was destroyed"), stale_element
    )

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)  # must not raise

    assert _navigated_url(iframe_locator) == f"{_SERVICE_URL}"


def test_transient_errors_during_polling_still_see_a_late_navigation(
    monkeypatch: pytest.MonkeyPatch,
):
    """The frame attaching after a failed read must still end the wait without a navigation."""
    page, iframe_locator = _page_with_service_iframe(iframe_content=_frame(_SERVICE_FRAME_URL))
    mock_page = cast("mock.Mock", page)
    monkeypatch.setattr(playwright_helpers, "_SERVICE_IFRAME_NAVIGATION_TIMEOUT", timedelta(seconds=1))
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_POLL_INTERVAL", timedelta(0))
    mock_page.query_selector.side_effect = _read_fails_then_returns(
        PlaywrightError("Execution context was destroyed"),
        cast("ElementHandle", mock_page.query_selector.return_value),
    )

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)

    iframe_locator.evaluate.assert_not_called()


def test_failing_service_iframe_navigation_is_not_raising(_no_service_iframe_waits: None):
    """A Playwright error during the best-effort navigation must not propagate.

    The service-ready helpers must fail with their own original error, not with an error from the
    recovery attempt.
    """
    page, _ = _page_with_service_iframe(
        iframe_content=_frame("about:blank"),
        evaluate_error=PlaywrightError("boom"),
    )

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)  # must not raise


def test_legacy_service_iframe_is_not_navigated(_no_service_iframe_waits: None):
    """A legacy service's iframe URL is its `service_basepath` plus the optional entry point, which
    the helper does not know; navigating it to the bare path could load the wrong page."""
    page, iframe_locator = _page_with_service_iframe(iframe_content=_frame("about:blank"))

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=True)

    iframe_locator.evaluate.assert_not_called()


def test_failing_service_iframe_probe_is_not_raising(_no_service_iframe_waits: None):
    """A Playwright error while probing the iframe must not propagate either."""
    page, _ = _page_with_service_iframe(iframe_content=None, query_selector_error=PlaywrightError("boom"))

    _ensure_service_iframe_attached(page, _NODE_ID, _SERVICE_URL, is_legacy_service=False)  # must not raise


def test_project_state_waiter_matches_state_frame_seen_before_project_uuid_is_set():
    # regression: opening a project publishes its state at the same time as the /projects/:open
    # response arrives, so the awaited frame can be received before the caller knows which project
    # to wait for. The waiter must remember that frame and match on it once the uuid is known.
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=(RunningState.STARTED,), project_uuid=None)

    assert waiter(_project_state_updated_message("project-a", RunningState.STARTED)) is False

    waiter.project_uuid = "project-a"

    assert waiter.is_done() is True


def test_project_state_waiter_keeps_only_frames_matching_the_late_known_project_uuid():
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=(RunningState.STARTED,), project_uuid=None)

    # an update of another project (e.g. one left open on this user by a previous run)
    assert waiter(_project_state_updated_message("project-b", RunningState.STARTED)) is False

    # the expected state of the project being opened, seen before its uuid was known
    assert waiter(_project_state_updated_message("project-a", RunningState.PUBLISHED)) is False

    waiter.project_uuid = "project-a"

    # neither frame satisfies the expectation: one has the wrong project, the other the wrong state
    assert waiter.is_done() is False

    assert waiter(_project_state_updated_message("project-a", RunningState.STARTED)) is True
    assert waiter.is_done() is True


def test_project_state_waiter_ignores_state_updates_for_other_project_uuid():
    waiter = SocketIOProjectStateUpdatedWaiter(
        expected_states=(RunningState.STARTED,),
        project_uuid="project-a",
    )

    done = waiter(_project_state_updated_message("project-b", RunningState.STARTED))

    assert done is False


def test_project_state_waiter_accepts_expected_state_for_matching_project_uuid():
    waiter = SocketIOProjectStateUpdatedWaiter(
        expected_states=(RunningState.STARTED,),
        project_uuid="project-a",
    )

    done = waiter(_project_state_updated_message("project-a", RunningState.STARTED))

    assert done is True


def test_project_closed_waiter_ignores_close_of_other_project_uuid():
    # regression: a project a previous job left open on this same user gets closed too, and its
    # close must not end the wait for the project this test is tearing down
    waiter = SocketIOProjectClosedWaiter(project_uuid="project-a")

    done = waiter(_project_share_state_message("project-b", status=ProjectStatus.CLOSED, locked=False))

    assert done is False


def test_project_closed_waiter_accepts_close_of_matching_project_uuid():
    waiter = SocketIOProjectClosedWaiter(project_uuid="project-a")

    done = waiter(_project_share_state_message("project-a", status=ProjectStatus.CLOSED, locked=False))

    assert done is True


def test_project_closed_waiter_ignores_a_project_that_is_still_open():
    waiter = SocketIOProjectClosedWaiter(project_uuid="project-a")

    done = waiter(_project_share_state_message("project-a", status=ProjectStatus.OPENED, locked=True))

    assert done is False


class _FakeEventContextManager:
    """Stands in for what `WebSocket.expect_event()` returns.
    NOTE:
    - entering it yields the pending event,
    - reading its `value` is what blocks until the event arrives
    - Playwright cancels a pending wait by exiting with an exception.
    """

    def __init__(self) -> None:
        self.value_read = False
        self.cancelled_with: list[BaseException] = []

    def __enter__(self) -> Self:
        return self

    @property
    def value(self) -> str:
        self.value_read = True
        return "42[]"

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_val is not None:
            self.cancelled_with.append(exc_val)


def _make_reconnectable_waiter(
    predicate: Callable[[str], bool],
) -> tuple[_ReconnectableEventWaiter, _FakeEventContextManager]:
    context_manager = _FakeEventContextManager()
    socket = SimpleNamespace(expect_event=lambda *_args, **_kwargs: context_manager)
    reconnectable = _ReconnectableEventWaiter(
        robust_websocket=cast(RobustWebSocket, SimpleNamespace(ws=socket)),
        event="framereceived",
        predicate=predicate,
        timeout=None,
    )
    return reconnectable, context_manager


def test_reconnectable_waiter_stops_waiting_when_the_predicate_already_saw_its_event():
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=(RunningState.STARTED,), project_uuid=None)
    assert waiter(_project_state_updated_message("project-a", RunningState.STARTED)) is False

    reconnectable, context_manager = _make_reconnectable_waiter(waiter)
    waiter.project_uuid = "project-a"

    reconnectable.__exit__(None, None, None)

    assert context_manager.value_read is False
    assert [type(exc) for exc in context_manager.cancelled_with] == [PlaywrightError]


def test_reconnectable_waiter_waits_for_an_event_when_the_predicate_is_not_satisfied():
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=(RunningState.STARTED,), project_uuid=None)
    assert waiter(_project_state_updated_message("project-a", RunningState.PUBLISHED)) is False

    reconnectable, context_manager = _make_reconnectable_waiter(waiter)
    waiter.project_uuid = "project-a"

    reconnectable.__exit__(None, None, None)

    assert context_manager.value_read is True
    assert context_manager.cancelled_with == []


_S4L_WS_URL: Final[str] = f"https://{_NODE_ID}.services.example.org/socket.io/?EIO=4&transport=websocket"
_WEBSOCKET_WAIT_TIMEOUT_MSG: Final[str] = 'Timeout 30000ms exceeded while waiting for event "websocket"'


class _FakeWebSocket:
    """Minimal `WebSocket` stand-in: records the listeners attached to it and reports its state."""

    def __init__(self, url: str, *, closed: bool = False) -> None:
        self.url = url
        self.closed = closed
        self.listeners: defaultdict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def on(self, event: str, listener: Callable[[Any], None]) -> None:
        self.listeners[event].append(listener)

    def emit(self, event: str, *args: Any) -> None:
        for listener in self.listeners[event]:
            listener(*args)

    def is_closed(self) -> bool:
        return self.closed


class _FakePage:
    """Minimal `Page` stand-in: records event listeners and the predicates of `expect_websocket` waits."""

    def __init__(self) -> None:
        self.listeners: defaultdict[str, list[Callable[[Any], None]]] = defaultdict(list)
        self.expect_websocket_calls = 0
        self.expect_websocket_predicates: list[Callable[[Any], bool]] = []
        self.expect_websocket_timeouts: list[float] = []

    def on(self, event: str, listener: Callable[[Any], None]) -> None:
        self.listeners[event].append(listener)

    def emit(self, event: str, *args: Any) -> None:
        for listener in self.listeners[event]:
            listener(*args)

    def expect_websocket(self, *args: Any, **kwargs: Any) -> Any:
        self.expect_websocket_calls += 1
        self.expect_websocket_predicates.append(args[0])
        self.expect_websocket_timeouts.append(kwargs["timeout"])
        _FAKE_MONOTONIC["seconds"] += _WEBSOCKET_WAIT_SLICE_S
        raise PlaywrightTimeoutError(_WEBSOCKET_WAIT_TIMEOUT_MSG)


def _connected_socket(page: _FakePage, url: str) -> _FakeWebSocket:
    """Hand ``url``'s socket to the page and let it receive its first frame."""
    socket = _FakeWebSocket(url)
    page.emit("websocket", socket)
    socket.emit("framereceived", "40")
    return socket


_FAKE_MONOTONIC: Final[dict[str, float]] = {"seconds": 0.0}
_WEBSOCKET_WAIT_SLICE_S: Final[float] = 3600.0


@pytest.fixture()
def _no_reconnect_retry_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the back-off sleeps between the reconnection attempts.

    ``time.monotonic`` is faked and advanced past any deadline by each (failed)
    `expect_websocket` wait, so the sliced reconnect wait makes exactly one
    attempt per tenacity retry.
    """
    _FAKE_MONOTONIC["seconds"] = 0.0
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr("time.monotonic", lambda: _FAKE_MONOTONIC["seconds"])


def test_start_websocket_tracking_records_each_page_socket_once():
    page = _FakePage()

    start_websocket_tracking(cast("Page", page))
    start_websocket_tracking(cast("Page", page))

    assert len(page.listeners["websocket"]) == 1


def test_robust_websocket_adopts_the_socket_that_reconnected_before_it_was_created():
    """Regression test for the master e2e failures.

    s4l-core's first handshake fails while it cold starts and its socket.io client then
    reconnects on its own, so the healthy socket can be created before the `RobustWebSocket`
    looking for it exists. Waiting for a *future* websocket event timed out three times in a row
    although a working connection was already there.
    """
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)
    live_socket = _connected_socket(page, _S4L_WS_URL)

    websocket = RobustWebSocket(page=cast("Page", page), ws=cast("WebSocket", dead_socket))

    assert websocket.ws is live_socket
    assert websocket._num_reconnections == 1  # noqa: SLF001
    assert page.expect_websocket_calls == 0


def test_robust_websocket_without_predicate_does_not_adopt_a_live_socket_on_another_endpoint(
    _no_reconnect_retry_waits: None,
):
    """A live connection to another endpoint is not the reconnection of this one."""
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)
    _connected_socket(page, "https://other-node.services.example.org/socket.io/?EIO=4&transport=websocket")

    with pytest.raises(PlaywrightTimeoutError):
        RobustWebSocket(page=cast("Page", page), ws=cast("WebSocket", dead_socket), reconnect_timeout=1)

    assert page.expect_websocket_calls > 0


def test_robust_websocket_does_not_adopt_a_socket_that_never_proved_its_handshake(
    _no_reconnect_retry_waits: None,
):
    """A socket.io connection refused by a cold-starting service still creates a socket: adopting
    a socket that received no frame would report a dead connection as healthy."""
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)
    handshaking_socket = _FakeWebSocket(_S4L_WS_URL)
    page.emit("websocket", handshaking_socket)

    with pytest.raises(PlaywrightTimeoutError):
        RobustWebSocket(page=cast("Page", page), ws=cast("WebSocket", dead_socket), reconnect_timeout=1)

    assert page.expect_websocket_calls > 0


def test_robust_websocket_falls_back_to_waiting_for_a_new_socket(_no_reconnect_retry_waits: None):
    """Without a tracked reconnection, the original wait for a new websocket must still run."""
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)

    with pytest.raises(PlaywrightTimeoutError):
        RobustWebSocket(page=cast("Page", page), ws=cast("WebSocket", dead_socket), reconnect_timeout=1)

    assert page.expect_websocket_calls == 3


def test_fallback_wait_only_accepts_a_socket_on_the_dead_sockets_endpoint(
    _no_reconnect_retry_waits: None,
):
    """Without a ws_predicate, a new socket on another URL is not this socket's reconnection."""
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)

    with pytest.raises(PlaywrightTimeoutError):
        RobustWebSocket(page=cast("Page", page), ws=cast("WebSocket", dead_socket), reconnect_timeout=1)

    accept = page.expect_websocket_predicates[0]
    reconnected_url = f"https://{_NODE_ID}.services.example.org/socket.io/?EIO=4&transport=websocket&sid=new"
    assert accept(_FakeWebSocket(reconnected_url))
    assert not accept(_FakeWebSocket("https://other-node.services.example.org/socket.io/?EIO=4"))
    assert not accept(_FakeWebSocket(reconnected_url, closed=True))


def test_robust_websocket_does_not_adopt_an_older_session_on_the_same_endpoint(
    _no_reconnect_retry_waits: None,
):
    """A session created before the wrapped socket is not its reconnection, even on its endpoint."""
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    _older_session = _connected_socket(page, _S4L_WS_URL)
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)
    page.emit("websocket", dead_socket)

    # the older session must not be adopted: without a tracked reconnection after the dead
    # socket, the wait falls through and fails instead of consuming the wrong session
    with pytest.raises(PlaywrightTimeoutError):
        RobustWebSocket(page=cast("Page", page), ws=cast("WebSocket", dead_socket), reconnect_timeout=1)

    assert page.expect_websocket_calls > 0


def test_robust_websocket_adopts_the_reconnection_next_to_an_older_session(_no_reconnect_retry_waits: None):
    """With an older live session on the endpoint, the socket created after the dead one wins."""
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    _connected_socket(page, _S4L_WS_URL)
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)
    page.emit("websocket", dead_socket)
    reconnected = _connected_socket(page, _S4L_WS_URL)

    websocket = RobustWebSocket(page=cast("Page", page), ws=cast("WebSocket", dead_socket))

    assert websocket.ws is reconnected
    assert page.expect_websocket_calls == 0


def test_robust_websocket_adopts_a_tracked_socket_matching_its_predicate(_no_reconnect_retry_waits: None):
    """The newest tracked socket failing the predicate must not stop the search for a matching one."""
    page = _FakePage()
    start_websocket_tracking(cast("Page", page))
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)
    matching_url = f"https://{_NODE_ID}.services.example.org/api/socket.io/?EIO=4&transport=websocket"
    matching = _connected_socket(page, matching_url)
    _connected_socket(page, _S4L_WS_URL)  # newer, on the dead socket's endpoint but rejected

    websocket = RobustWebSocket(
        page=cast("Page", page),
        ws=cast("WebSocket", dead_socket),
        ws_predicate=lambda ws: ws.url == matching_url,
    )

    assert websocket.ws is matching
    assert page.expect_websocket_calls == 0


class _SocketHandshakingDuringWaitPage(_FakePage):
    """Answers the first websocket wait with the handshake completion of ``late_socket``.

    Models a socket whose creation event was delivered before the wait was entered: it can never
    satisfy `expect_websocket`, only the registry re-check between wait slices can find it.
    """

    def __init__(self, late_socket: _FakeWebSocket) -> None:
        super().__init__()
        self.late_socket = late_socket

    def expect_websocket(self, *args: Any, **kwargs: Any) -> Any:
        if self.expect_websocket_calls == 0:
            self.emit("websocket", self.late_socket)
            self.late_socket.emit("framereceived", "40")
        return super().expect_websocket(*args, **kwargs)


def test_reconnecting_socket_handshaking_during_the_creation_wait_is_adopted(
    _no_reconnect_retry_waits: None,
):
    """The registry re-check after a timed-out slice must adopt the now-live socket,
    and each wait must be requested in a slice, never for the full reconnect timeout."""
    reconnected = _FakeWebSocket(_S4L_WS_URL)
    page = _SocketHandshakingDuringWaitPage(reconnected)
    start_websocket_tracking(cast("Page", page))
    dead_socket = _FakeWebSocket(_S4L_WS_URL, closed=True)

    # timeout larger than one slice, so a wait for the full timeout would be detectable
    reconnect_timeout = 10 * playwright_helpers._WEBSOCKET_CREATION_WAIT_SLICE  # noqa: SLF001
    websocket = RobustWebSocket(
        page=cast("Page", page), ws=cast("WebSocket", dead_socket), reconnect_timeout=reconnect_timeout
    )

    assert websocket.ws is reconnected
    assert websocket._num_reconnections == 1  # noqa: SLF001
    assert page.expect_websocket_calls == 1
    assert (
        page.expect_websocket_timeouts[0] == playwright_helpers._WEBSOCKET_CREATION_WAIT_SLICE  # noqa: SLF001
    )
