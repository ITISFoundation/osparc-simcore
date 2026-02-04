from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.projects_nodes_io import NodeID

from ..base_repository import get_repository
from ._models import StepId
from ._notifications import NotificationsManager
from ._repositories.user_requests import UserRequestsRepository
from ._workflow_manager import WorkflowManager


async def request_present(app: FastAPI, node_id: NodeID, dynamic_service_start: DynamicServiceStart) -> None:
    user_requests_repo = get_repository(app, UserRequestsRepository)
    await user_requests_repo.request_service_present(node_id, dynamic_service_start)

    notifications_manager = NotificationsManager.get_from_app_state(app)
    await notifications_manager.send_riconciliation_event(node_id)


async def request_absent(app: FastAPI, node_id: NodeID, dynamic_service_stop: DynamicServiceStop) -> None:
    user_requests_repo = get_repository(app, UserRequestsRepository)
    await user_requests_repo.request_service_absent(node_id, dynamic_service_stop)

    notifications_manager = NotificationsManager.get_from_app_state(app)
    await notifications_manager.send_riconciliation_event(node_id)


async def retry_step(app: FastAPI, node_id: NodeID, step_id: StepId) -> None:
    workflow_manager = WorkflowManager.get_from_app_state(app)
    await workflow_manager.retry_workflow_step(node_id, step_id)


async def skip_step(app: FastAPI, node_id: NodeID, step_id: StepId) -> None:
    workflow_manager = WorkflowManager.get_from_app_state(app)
    await workflow_manager.skip_workflow_step(node_id, step_id)
