"""
States from Docker Tasks and docker Containers are mapped to ServiceState.
"""
import logging
from typing import Dict, Set, Tuple

from ...models.schemas.dynamic_services import ServiceState

logger = logging.getLogger(__name__)

# For all available task states SEE
# https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/
TASK_STATES_FAILED: Set[str] = {"failed", "rejected", "orphaned"}
TASK_STATES_PENDING: Set[str] = {"new", "assigned", "accepted", "pending"}
TASK_STATES_PULLING: Set[str] = {"preparing"}
TASK_STATES_STARTING: Set[str] = {"ready", "starting"}
TASK_STATES_RUNNING: Set[str] = {"running"}
TASK_STATES_COMPLETE: Set[str] = {"complete", "shutdown", "remove"}


TASK_STATES_ALL: Set[str] = (
    TASK_STATES_FAILED
    | TASK_STATES_PENDING
    | TASK_STATES_PULLING
    | TASK_STATES_STARTING
    | TASK_STATES_RUNNING
    | TASK_STATES_COMPLETE
)


# mapping container states into 4 categories
# For all avaliable containerstates SEE
# https://github.com/moby/moby/blob/master/container/state.go#L140
CONTAINER_STATUSES_FAILED: Set[str] = {"restarting", "dead", "paused"}
CONTAINER_STATUSES_STARTING: Set[str] = {"created"}
CONTAINER_STATUSES_RUNNING: Set[str] = {"running"}
CONTAINER_STATUSES_COMPLETE: Set[str] = {"removing", "exited"}


_TASK_STATE_TO_SERVICE_STATE: Dict[str, ServiceState] = {
    **dict.fromkeys(TASK_STATES_FAILED, ServiceState.FAILED),
    **dict.fromkeys(TASK_STATES_PENDING, ServiceState.PENDING),
    **dict.fromkeys(TASK_STATES_PULLING, ServiceState.PULLING),
    **dict.fromkeys(TASK_STATES_STARTING, ServiceState.STARTING),
    **dict.fromkeys(TASK_STATES_RUNNING, ServiceState.RUNNING),
    **dict.fromkeys(TASK_STATES_COMPLETE, ServiceState.COMPLETE),
}


_CONTAINER_STATE_TO_SERVICE_STATE: Dict[str, ServiceState] = {
    **dict.fromkeys(CONTAINER_STATUSES_FAILED, ServiceState.FAILED),
    **dict.fromkeys(CONTAINER_STATUSES_STARTING, ServiceState.STARTING),
    **dict.fromkeys(CONTAINER_STATUSES_RUNNING, ServiceState.RUNNING),
    **dict.fromkeys(CONTAINER_STATUSES_COMPLETE, ServiceState.COMPLETE),
}


def extract_task_state(task_status: Dict[str, str]) -> Tuple[ServiceState, str]:
    last_task_error_msg = task_status["Err"] if "Err" in task_status else ""

    task_state = _TASK_STATE_TO_SERVICE_STATE[task_status["State"]]
    return (task_state, last_task_error_msg)


def _extract_container_status(
    container_status: Dict[str, str]
) -> Tuple[ServiceState, str]:
    last_task_error_msg = (
        container_status["Error"] if "Error" in container_status else ""
    )

    container_state = _CONTAINER_STATE_TO_SERVICE_STATE[container_status["Status"]]
    return (container_state, last_task_error_msg)


def extract_containers_minimim_statuses(
    containers_status: Dict[str, Dict[str, str]]
) -> Tuple[ServiceState, str]:
    """
    Because more then one container can be started by the dynamic-sidecar,
    the lowest (considered worst) state will be forwarded to the frontend.
    `ServiceState` defines the order of the states.
    """
    logger.info("containers_status=%s", containers_status)
    remapped_service_statuses = {
        k: _extract_container_status(value)
        for k, value in enumerate(containers_status.values())
    }
    result: Tuple[ServiceState, str] = min(
        remapped_service_statuses.values(), key=lambda x: x
    )
    return result
