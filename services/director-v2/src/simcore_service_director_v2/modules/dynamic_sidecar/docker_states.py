"""
States from Docker Tasks and docker Containers are mapped to ServiceState.
"""
import logging
from enum import Enum
from functools import total_ordering
from typing import Dict, Set, Tuple

logger = logging.getLogger(__name__)

TASK_STATES_FAILED: Set[str] = {"failed", "rejected"}
TASK_STATES_PENDING: Set[str] = {"pending"}
TASK_STATES_PULLING: Set[str] = {"assigned", "accepted", "preparing"}
TASK_STATES_STARTING: Set[str] = {"ready", "starting"}
TASK_STATES_RUNNING: Set[str] = {"running"}
TASK_STATES_COMPLETE: Set[str] = {"complete", "shutdown"}


TASK_STATES_ALL: Set[str] = (
    TASK_STATES_FAILED
    | TASK_STATES_PENDING
    | TASK_STATES_PULLING
    | TASK_STATES_STARTING
    | TASK_STATES_RUNNING
    | TASK_STATES_COMPLETE
)


# mapping container states into 4 categories
CONTAINER_STATES_FAILED: Set[str] = {"restarting", "dead", "paused"}
CONTAINER_STATES_PENDING: Set[str] = {"pending"}  # fake state
CONTAINER_STATES_PULLING: Set[str] = {"pulling"}  # fake state
CONTAINER_STATES_STARTING: Set[str] = {"created"}
CONTAINER_STATES_RUNNING: Set[str] = {"running"}
CONTAINER_STATES_COMPLETE: Set[str] = {"removing", "exited"}


@total_ordering
class ServiceState(Enum):
    """
    `Docker Task` and `Docker Container` states are remapped to this `Service State`
    These states need to be comparable in a predefined order,
    see _SERVICE_STATE_COMPARISON_ORDER below.
    """

    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            self_index = _SERVICE_STATE_COMPARISON_ORDER[self]
            other_index = _SERVICE_STATE_COMPARISON_ORDER[other]
            return self_index < other_index
        return NotImplemented


# defines the order in which the fields should be sorted
# without having to change the values of each enum property
_SERVICE_STATE_COMPARISON_ORDER: Dict[ServiceState, int] = {
    ServiceState.PENDING: 0,
    ServiceState.PULLING: 1,
    ServiceState.STARTING: 2,
    ServiceState.RUNNING: 3,
    ServiceState.COMPLETE: 4,
    ServiceState.FAILED: 5,
}


def _docker_task_state_to_service_state(state: str) -> ServiceState:
    last_state = ServiceState.STARTING  # default

    if state in TASK_STATES_FAILED:
        last_state = ServiceState.FAILED
    elif state in TASK_STATES_PENDING:
        last_state = ServiceState.PENDING
    elif state in TASK_STATES_PULLING:
        last_state = ServiceState.PULLING
    elif state in TASK_STATES_STARTING:
        last_state = ServiceState.STARTING
    elif state in TASK_STATES_RUNNING:
        last_state = ServiceState.RUNNING
    elif state in TASK_STATES_COMPLETE:
        last_state = ServiceState.COMPLETE

    return last_state


def _docker_container_state_to_service_state(state: str) -> ServiceState:
    last_state = ServiceState.STARTING  # default

    if state in CONTAINER_STATES_FAILED:
        last_state = ServiceState.FAILED
    elif state in CONTAINER_STATES_PENDING:
        last_state = ServiceState.PENDING
    elif state in CONTAINER_STATES_PULLING:
        last_state = ServiceState.PULLING
    elif state in CONTAINER_STATES_STARTING:
        last_state = ServiceState.STARTING
    elif state in CONTAINER_STATES_RUNNING:
        last_state = ServiceState.RUNNING
    elif state in CONTAINER_STATES_COMPLETE:
        last_state = ServiceState.COMPLETE

    return last_state


def extract_task_state(task_status: Dict[str, str]) -> Tuple[ServiceState, str]:
    last_task_error_msg = task_status["Err"] if "Err" in task_status else ""

    task_state = _docker_task_state_to_service_state(state=task_status["State"])
    return (task_state, last_task_error_msg)


def _extract_container_status(
    container_status: Dict[str, str]
) -> Tuple[ServiceState, str]:
    last_task_error_msg = (
        container_status["Error"] if "Error" in container_status else ""
    )

    container_state = _docker_container_state_to_service_state(
        state=container_status["Status"]
    )
    return (container_state, last_task_error_msg)


def extract_containers_minimim_statuses(
    containers_status: Dict[str, Dict[str, str]]
) -> Tuple[ServiceState, str]:
    logger.info("containers_status=%s", containers_status)
    remapped_service_statuses = {
        k: _extract_container_status(value)
        for k, value in enumerate(containers_status.values())
    }
    result: Tuple[ServiceState, str] = min(
        remapped_service_statuses.values(), key=lambda x: x
    )
    return result
