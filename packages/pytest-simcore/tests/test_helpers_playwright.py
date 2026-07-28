# pylint: disable=protected-access

import json
from datetime import timedelta

from pytest_simcore.helpers.playwright import (
    SOCKETIO_MESSAGE_PREFIX,
    NodeProgressType,
    SocketIONodeProgressCompleteWaiter,
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
    waiter._first_service_status_received_at -= timedelta(seconds=20)  # noqa: SLF001

    second_done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert second_done is True
    assert waiter.success is False


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
