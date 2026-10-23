# pylint: disable=protected-access

import json
from collections.abc import Callable
from datetime import timedelta
from types import SimpleNamespace, TracebackType
from typing import Any, Self, cast

from models_library.projects_state import ProjectStatus, RunningState
from models_library.rabbitmq_messages import ProgressType
from playwright.sync_api import Error as PlaywrightError
from pytest_simcore.helpers.playwright import (
    REQUIRED_PROGRESS_TYPES_FOR_STARTED_SERVICE,
    SOCKETIO_MESSAGE_PREFIX,
    RobustWebSocket,
    SocketIONodeProgressCompleteWaiter,
    SocketIOProjectClosedWaiter,
    SocketIOProjectStateUpdatedWaiter,
    _ReconnectableEventWaiter,
)

_NODE_ID = "d00cb7e0-8b78-4d5c-9b57-2a1f6c6a1234"


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
    # NOTE: regression test — an idle SERVICE_STATUS message that stays within
    # its own idle grace period must not bypass the general stale-progress
    # fallback check (`max_idle_timeout`), otherwise the waiter could wait
    # forever if the backend keeps reporting "idle" but never emits any
    # nodeProgress message.
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
