import inspect
import logging
from datetime import timedelta
from typing import Final

import arrow
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.services_enums import ServiceState
from models_library.users import UserID
from servicelib.deferred_tasks import TaskUID

from ._models import SchedulerServiceState, TrackedServiceModel, UserRequestedState
from ._setup import get_tracker

_logger = logging.getLogger(__name__)


_LOW_RATE_POLL_INTERVAL: Final[timedelta] = timedelta(seconds=1)
NORMAL_RATE_POLL_INTERVAL: Final[timedelta] = timedelta(seconds=5)
_MAX_PERIOD_WITHOUT_SERVICE_STATUS_UPDATES: Final[timedelta] = timedelta(seconds=60)


async def set_request_as_running(
    app: FastAPI,
    dynamic_service_start: DynamicServiceStart,
) -> None:
    """Stores intention to `start` request"""
    await get_tracker(app).save(
        dynamic_service_start.node_uuid,
        TrackedServiceModel(
            dynamic_service_start=dynamic_service_start,
            requested_state=UserRequestedState.RUNNING,
            project_id=dynamic_service_start.project_id,
            user_id=dynamic_service_start.user_id,
        ),
    )


async def set_request_as_stopped(
    app: FastAPI, dynamic_service_stop: DynamicServiceStop
) -> None:
    """Stores intention to `stop` request"""
    tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(dynamic_service_stop.node_id)

    if model is None:
        model = TrackedServiceModel(
            dynamic_service_start=None,
            user_id=dynamic_service_stop.user_id,
            project_id=dynamic_service_stop.project_id,
            requested_state=UserRequestedState.STOPPED,
        )

    model.requested_state = UserRequestedState.STOPPED
    await tracker.save(dynamic_service_stop.node_id, model)


def _get_service_state(
    status: NodeGet | DynamicServiceGet | NodeGetIdle,
) -> ServiceState:
    # Attributes where to find the state
    # NodeGet -> service_state
    # DynamicServiceGet -> state
    # NodeGetIdle -> service_state
    state_key = "state" if isinstance(status, DynamicServiceGet) else "service_state"

    state: ServiceState | str = getattr(status, state_key)
    result: str = state.value if isinstance(state, ServiceState) else state
    return ServiceState(result)


def _get_poll_interval(status: NodeGet | DynamicServiceGet | NodeGetIdle) -> timedelta:
    if _get_service_state(status) != ServiceState.RUNNING:
        return _LOW_RATE_POLL_INTERVAL

    return NORMAL_RATE_POLL_INTERVAL


def _get_current_scheduler_service_state(
    requested_state: UserRequestedState,
    status: NodeGet | DynamicServiceGet | NodeGetIdle,
) -> SchedulerServiceState:
    """
    Computes the `SchedulerServiceState` used internally by the scheduler
    to decide about a service's future.
    """

    if isinstance(status, NodeGetIdle):
        return SchedulerServiceState.IDLE

    service_state: ServiceState = _get_service_state(status)

    if requested_state == UserRequestedState.RUNNING:
        if service_state == ServiceState.RUNNING:
            return SchedulerServiceState.RUNNING

        if (
            ServiceState.PENDING  # type:ignore[operator]
            <= service_state
            <= ServiceState.STARTING
        ):
            return SchedulerServiceState.STARTING

        if service_state < ServiceState.PENDING or service_state > ServiceState.RUNNING:
            return SchedulerServiceState.UNEXPECTED_OUTCOME

    if requested_state == UserRequestedState.STOPPED:
        if service_state >= ServiceState.RUNNING:  # type:ignore[operator]
            return SchedulerServiceState.STOPPING

        if service_state < ServiceState.RUNNING:
            return SchedulerServiceState.UNEXPECTED_OUTCOME

    msg = f"Could not determine current_state from: '{requested_state=}', '{status=}'"
    raise TypeError(msg)


def _log_skipping_operation(node_id: NodeID) -> None:
    # the caller is at index 1 (index 0 is the current function)
    caller_name = inspect.stack()[1].function

    _logger.info(
        "Could not find a %s entry for node_id %s: skipping %s",
        TrackedServiceModel.__name__,
        node_id,
        caller_name,
    )


async def set_if_status_changed_for_service(
    app: FastAPI, node_id: NodeID, status: NodeGet | DynamicServiceGet | NodeGetIdle
) -> bool:
    """returns ``True`` if the tracker detected a status change"""
    tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)
    if model is None:
        _log_skipping_operation(node_id)
        return False

    # set new polling interval in the future
    model.set_check_status_after_to(_get_poll_interval(status))
    model.service_status_task_uid = None
    model.scheduled_to_run = False

    # check if model changed
    json_status = status.model_dump_json()
    if model.service_status != json_status:
        model.service_status = json_status
        model.current_state = _get_current_scheduler_service_state(
            model.requested_state, status
        )
        await tracker.save(node_id, model)
        return True

    return False


async def should_notify_frontend_for_service(
    app: FastAPI, node_id: NodeID, *, status_changed: bool
) -> bool:
    """
    Checks if it's time to notify the frontend.
    The frontend will be notified at regular intervals and on changes
    Avoids sending too many updates.
    """
    tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)

    if model is None:
        return False

    # check if too much time has passed since the last time an update was sent
    return (
        status_changed
        or arrow.utcnow().timestamp() - model.last_status_notification
        > _MAX_PERIOD_WITHOUT_SERVICE_STATUS_UPDATES.total_seconds()
    )


async def set_frontned_notified_for_service(app: FastAPI, node_id: NodeID) -> None:
    tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)
    if model is None:
        _log_skipping_operation(node_id)
        return

    model.set_last_status_notification_to_now()
    await tracker.save(node_id, model)


async def set_service_scheduled_to_run(
    app: FastAPI, node_id: NodeID, delay_from_now: timedelta
) -> None:
    tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)
    if model is None:
        _log_skipping_operation(node_id)
        return

    model.scheduled_to_run = True
    model.set_check_status_after_to(delay_from_now)
    await tracker.save(node_id, model)


async def set_service_status_task_uid(
    app: FastAPI, node_id: NodeID, task_uid: TaskUID
) -> None:
    tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)
    if model is None:
        _log_skipping_operation(node_id)
        return

    model.service_status_task_uid = task_uid
    await tracker.save(node_id, model)


async def remove_tracked_service(app: FastAPI, node_id: NodeID) -> None:
    """
    Removes the service from tracking (usually after stop completes)
    # NOTE: does not raise if node_id is not found
    """
    await get_tracker(app).delete(node_id)


async def get_tracked_service(
    app: FastAPI, node_id: NodeID
) -> TrackedServiceModel | None:
    """Returns information about the tracked service"""
    return await get_tracker(app).load(node_id)


async def get_all_tracked_services(app: FastAPI) -> dict[NodeID, TrackedServiceModel]:
    """Returns all tracked services"""
    return await get_tracker(app).all()


async def get_user_id_for_service(app: FastAPI, node_id: NodeID) -> UserID | None:
    """returns user_id for the service"""
    model: TrackedServiceModel | None = await get_tracker(app).load(node_id)
    return model.user_id if model else None
