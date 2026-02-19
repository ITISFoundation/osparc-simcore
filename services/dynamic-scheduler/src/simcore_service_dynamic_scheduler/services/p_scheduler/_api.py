from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.projects_nodes_io import NodeID

from ..base_repository import get_repository
from ._models import StepFailHistory, StepId, WorkflowDefinition, WorkflowName
from ._notifications import NotificationsManager
from ._repositories import UserRequestsRepository
from ._workflow_manager import WorkflowManager
from ._workflow_registry import WorkflowRegistry


async def request_present(app: FastAPI, node_id: NodeID, dynamic_service_start: DynamicServiceStart) -> None:
    user_requests_repo = get_repository(app, UserRequestsRepository)
    await user_requests_repo.request_service_present(dynamic_service_start)

    notifications_manager = NotificationsManager.get_from_app_state(app)
    await notifications_manager.send_riconciliation_event(node_id)


async def request_absent(app: FastAPI, node_id: NodeID, dynamic_service_stop: DynamicServiceStop) -> None:
    user_requests_repo = get_repository(app, UserRequestsRepository)
    await user_requests_repo.request_service_absent(dynamic_service_stop)

    notifications_manager = NotificationsManager.get_from_app_state(app)
    await notifications_manager.send_riconciliation_event(node_id)


async def retry_step(app: FastAPI, node_id: NodeID, step_id: StepId, *, reason: str) -> None:
    """Used by the admin UI to retry a failed step of a workflow run, in order to unblock the workflow execution."""
    workflow_manager = WorkflowManager.get_from_app_state(app)
    await workflow_manager.retry_workflow_step(node_id, step_id, reason)


async def skip_step(app: FastAPI, node_id: NodeID, step_id: StepId, *, reason: str) -> None:
    """Used by the admin UI to skip a failed step of a workflow run, in order to unblock the workflow execution."""
    workflow_manager = WorkflowManager.get_from_app_state(app)
    await workflow_manager.skip_workflow_step(node_id, step_id, reason)


async def get_step_fail_history(app: FastAPI, step_id: StepId) -> list[StepFailHistory]:
    """Used by the admin UI to display information on a failed step of a workflow run"""
    workflow_manager = WorkflowManager.get_from_app_state(app)
    return await workflow_manager.get_step_fail_history(step_id)


def register_workflow(app: FastAPI, name: WorkflowName, definition: WorkflowDefinition) -> None:
    workflow_manager = WorkflowRegistry.get_from_app_state(app)
    workflow_manager.register_workflow(name, definition)
