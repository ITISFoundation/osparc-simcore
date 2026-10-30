# pylint: disable=protected-access

import json
from collections.abc import Callable
from datetime import timedelta
from types import SimpleNamespace, TracebackType
from typing import Any, Final, Self, cast
from unittest import mock

import pytest
from models_library.projects_state import ProjectStatus, RunningState
from models_library.rabbitmq_messages import ProgressType
from playwright.sync_api import ElementHandle, Frame, Locator, Page
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
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


def _frame(url: str) -> Frame:
    frame = mock.create_autospec(Frame, instance=True)
    frame.url = url
    return frame


def _page_with_service_iframe(
    *,
    first_iframe_content: Frame | None,
    iframe_src_set: bool = True,
    evaluate_error: Exception | None = None,
    attached_duplicate: bool = False,
) -> tuple[Page, mock.Mock]:
    """Autospecced `Page` whose service iframe element attaches ``first_iframe_content``.

    Returns the page and the `Locator` the helper uses to reach the iframe
    element, so that tests can observe the recovery re-navigation. With
    ``attached_duplicate``, an attached duplicate frame is visible only through
    ``page.frames``, never on the first iframe element.
    """
    page = mock.create_autospec(Page, instance=True)
    iframe_locator = mock.create_autospec(Locator, instance=True)
    iframe_element = mock.create_autospec(ElementHandle, instance=True)

    iframe_locator.first = iframe_locator
    iframe_locator.element_handle.return_value = iframe_element
    iframe_element.content_frame.return_value = first_iframe_content
    if evaluate_error is not None:
        iframe_locator.evaluate.side_effect = evaluate_error
    page.evaluate.return_value = iframe_src_set
    if attached_duplicate:
        page.frames = [_frame(_SERVICE_FRAME_URL)]
    page.locator.return_value = iframe_locator
    return page, iframe_locator


@pytest.fixture()
def _no_frame_attach_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the content-frame attachment grace window of the helper."""
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_ATTACH_TIMEOUT", timedelta(0))


@pytest.fixture()
def _no_src_wait_grace(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the iframe-source wait window of the helper."""
    monkeypatch.setattr(playwright_helpers, "_SERVICE_IFRAME_SRC_TIMEOUT", timedelta(0))
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_POLL_INTERVAL", timedelta(0))


def test_healthy_service_iframe_is_left_untouched():
    page, iframe_locator = _page_with_service_iframe(first_iframe_content=_frame(_SERVICE_FRAME_URL))

    _ensure_service_iframe_attached(page, _NODE_ID)

    iframe_locator.evaluate.assert_not_called()


def test_unattached_service_iframe_is_re_navigated(_no_frame_attach_grace: None):
    """Regression test for microsoft/playwright#43007.

    The service UI is rendered but its content frame never attaches, so the
    driver keeps exposing the stale frame of the previous navigation and
    queries hang forever.
    """
    page, iframe_locator = _page_with_service_iframe(first_iframe_content=_frame("about:blank"))

    _ensure_service_iframe_attached(page, _NODE_ID)

    iframe_locator.evaluate.assert_called_once()


def test_unattached_first_service_iframe_is_re_navigated_despite_attached_duplicate(
    _no_frame_attach_grace: None,
):
    """An attached duplicate must not mask the unattached first iframe.

    Regression test: with duplicate service iframes, the first one is what the
    returned `FrameLocator` queries.
    """
    page, iframe_locator = _page_with_service_iframe(first_iframe_content=None, attached_duplicate=True)

    _ensure_service_iframe_attached(page, _NODE_ID)

    iframe_locator.evaluate.assert_called_once()


def test_late_service_iframe_navigation_is_still_rescued(
    _no_frame_attach_grace: None,
    monkeypatch: pytest.MonkeyPatch,
):
    """Regression test: timing out on the iframe src must not abort the helper.

    The UI sets the src late here (its readiness polling trails the backend)
    and the frame never attaches, so only the re-navigation can recover it.
    Pre-fix, the src wait raised TimeoutError and the recovery never ran.
    """
    page, iframe_locator = _page_with_service_iframe(first_iframe_content=_frame("about:blank"))
    mock_page = cast("mock.Mock", page)
    mock_page.evaluate.side_effect = [False, False, True]
    # the pre-fix helper waited on wait_for_function and aborted on its timeout;
    # fail it so this test reproduces that path
    mock_page.wait_for_function.side_effect = PlaywrightTimeoutError("Timeout")
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_POLL_INTERVAL", timedelta(0))

    _ensure_service_iframe_attached(page, _NODE_ID)

    iframe_locator.evaluate.assert_called_once()


def test_service_iframe_not_navigated_yet_is_left_untouched(_no_src_wait_grace: None):
    """An iframe the UI has not navigated yet must not be treated as the attach failure.

    Regression test: the UI assigns the iframe src asynchronously, so reloading
    it here would restart a healthy navigation.
    """
    page, iframe_locator = _page_with_service_iframe(first_iframe_content=None, iframe_src_set=False)

    _ensure_service_iframe_attached(page, _NODE_ID)

    iframe_locator.evaluate.assert_not_called()


def test_failing_iframe_recovery_is_not_raising(_no_frame_attach_grace: None):
    """A Playwright error during the best-effort recovery must not propagate.

    The service-ready helpers must fail with their own original error, not with
    an error from the recovery attempt.
    """
    page, _ = _page_with_service_iframe(
        first_iframe_content=_frame("about:blank"),
        evaluate_error=PlaywrightError("boom"),
    )

    _ensure_service_iframe_attached(page, _NODE_ID)  # must not raise


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
