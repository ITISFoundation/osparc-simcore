# pylint: disable=protected-access

import json
from datetime import timedelta

from pytest_simcore.helpers.playwright import (
    SOCKETIO_MESSAGE_PREFIX,
    NodeProgressType,
    RunningState,
    SocketIONodeProgressCompleteWaiter,
    SocketIOProjectStateUpdatedWaiter,
)

_NODE_ID = "d00cb7e0-8b78-4d5c-9b57-2a1f6c6a1234"


def _socketio_message(name: str, obj: dict) -> str:
    return f"{SOCKETIO_MESSAGE_PREFIX}{json.dumps([name, obj])}"


def _service_status_message(node_id: str, service_state: str) -> str:
    return _socketio_message("serviceStatus", {"service_uuid": node_id, "service_state": service_state})


def _node_progress_message(node_id: str, progress_type: NodeProgressType, ratio: float) -> str:
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

    required_types = sorted(NodeProgressType.required_types_for_started_service(), key=lambda t: t.value)
    done = False
    for progress_type in required_types:
        done = waiter(_node_progress_message(_NODE_ID, progress_type, 1.0))

    assert done is True
    assert waiter.success is True


def test_project_state_waiter_ignores_project_updates_until_project_uuid_is_set():
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=(RunningState.STARTED,))

    done = waiter(_project_state_updated_message("project-a", RunningState.STARTED))

    assert done is False


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
