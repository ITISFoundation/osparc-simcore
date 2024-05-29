from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ._models import TrackedServiceModel, UserRequestedState
from ._setup import get_tracker
from ._tracker import Tracker


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


# TODO: call this when user requests the start of a service
async def set_tracked_as_running(app: FastAPI, node_id: NodeID) -> None:
    """Stores the intention fo the user: ``start`` requested"""
    await _set_requested_state(app, node_id, UserRequestedState.RUNNING)


# TODO: call this when user requests the stop of a service
async def set_tracked_as_stopped(app: FastAPI, node_id: NodeID) -> None:
    """Stores the intention of the user: ``stop`` requested"""
    await _set_requested_state(app, node_id, UserRequestedState.STOPPED)


# TODO: call this when can no longer find the service
async def remove_tracked(app: FastAPI, node_id: NodeID) -> None:
    """Removes the service from tracking (usually after stop completes)"""
    tracker: Tracker = get_tracker(app)
    await tracker.delete(node_id)


async def get_tracked(app: FastAPI, node_id: NodeID) -> TrackedServiceModel | None:
    """Returns information about the tracked service"""
    tracker: Tracker = get_tracker(app)
    return await tracker.load(node_id)


# TODO: figure out if we want to emit events for this in order for other parts to react properly and how to handle all these events
