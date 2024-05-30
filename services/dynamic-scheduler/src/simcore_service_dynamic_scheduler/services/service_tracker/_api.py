import logging

from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from servicelib.deferred_tasks import TaskUID

from ._models import TrackedServiceModel, UserRequestedState
from ._setup import get_tracker
from ._tracker import Tracker

_logger = logging.getLogger(__name__)


async def _set_requested_state(
    app: FastAPI, node_id: NodeID, requested_state: UserRequestedState
) -> None:
    tracker: Tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)
    if model is None:
        model = TrackedServiceModel(requested_sate=requested_state)
    else:
        model.requested_sate = requested_state
    await tracker.save(node_id, model)


async def set_request_as_running(app: FastAPI, node_id: NodeID) -> None:
    """Stores the intention fo the user: ``start`` requested"""
    await _set_requested_state(app, node_id, UserRequestedState.RUNNING)


async def set_request_as_stopped(app: FastAPI, node_id: NodeID) -> None:
    """Stores the intention of the user: ``stop`` requested"""
    await _set_requested_state(app, node_id, UserRequestedState.STOPPED)


async def set_new_status(
    app: FastAPI, node_id: NodeID, status: NodeGet | DynamicServiceGet | NodeGetIdle
) -> None:
    tracker: Tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)
    if model is None:
        _logger.info(
            "Could not find a %s entry for node_id %s: skipping set_new_status",
            TrackedServiceModel.__name__,
            node_id,
        )
        return

    model.service_status = status.json()
    model.set_last_checked_to_now()
    model.service_status_task_uid = None
    await tracker.save(node_id, model)


async def set_service_status_task_uid(
    app: FastAPI, node_id: NodeID, task_uid: TaskUID
) -> None:
    tracker: Tracker = get_tracker(app)
    model: TrackedServiceModel | None = await tracker.load(node_id)
    if model is None:
        _logger.info(
            "Could not find a %s entry for node_id %s: skipping set_service_status_task_uid",
            TrackedServiceModel.__name__,
            node_id,
        )
        return

    model.service_status_task_uid = task_uid
    await tracker.save(node_id, model)


async def remove_tracked(app: FastAPI, node_id: NodeID) -> None:
    """Removes the service from tracking (usually after stop completes)"""
    # NOTE: does not raise if node_id is not found
    tracker: Tracker = get_tracker(app)
    await tracker.delete(node_id)


async def get_tracked(app: FastAPI, node_id: NodeID) -> TrackedServiceModel | None:
    """Returns information about the tracked service"""
    tracker: Tracker = get_tracker(app)
    return await tracker.load(node_id)


async def get_all_tracked(app: FastAPI) -> dict[NodeID, TrackedServiceModel]:
    """Returns all tracked services"""
    tracker: Tracker = get_tracker(app)
    return await tracker.all()
