import logging
from functools import cached_property
from typing import Final

from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from simcore_service_dynamic_scheduler.services.p_scheduler._models import UserRequest

from ..base_repository import get_repository
from ._models import Run, Step, StepId
from ._repositories import RunsRepository, StepsRepository, UserRequestsRepository

_logger = logging.getLogger(__name__)

_START: Final[str] = "START"
_STOP: Final[str] = "STOP"


class UnexpectedWorkflowManagerError(Exception): ...


async def _ensure_user_request(user_requests_repo: UserRequestsRepository, node_id: NodeID) -> UserRequest:
    user_request = await user_requests_repo.get_user_request(node_id)
    if user_request is None:
        msg = f"No user request found for node_id={node_id}"
        raise UnexpectedWorkflowManagerError(msg)
    return user_request


async def _ensure_current_run(runs_repo: RunsRepository, node_id: NodeID) -> Run:
    run = await runs_repo.get_run_from_node_id(node_id)
    if run is None:
        msg = f"No active run found for node_id={node_id}"
        raise UnexpectedWorkflowManagerError(msg)
    return run


async def _validate_workflow_creation_preconditions(
    node_id: NodeID,
    runs_repo: RunsRepository,
    user_requests_repo: UserRequestsRepository,
    payload_type: type[DynamicServiceStart] | type[DynamicServiceStop],
) -> UserRequest:
    user_request = await _ensure_user_request(user_requests_repo, node_id)

    query_run = await runs_repo.get_run_from_node_id(node_id)
    if query_run is not None:
        msg = f"A {query_run=} was found for {node_id=}"
        raise UnexpectedWorkflowManagerError(msg)

    method_name = _START if payload_type is DynamicServiceStart else _STOP

    if not isinstance(user_request.payload, payload_type):
        msg = f"Wrong {method_name} payload for node_id={node_id} with user_request={user_request}"
        raise UnexpectedWorkflowManagerError(msg)

    return user_request


class WorkflowManager(SingletonInAppStateMixin):
    app_state_name: str = "p_scheduler_workflow_manager"

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    @cached_property
    def user_requests_repo(self) -> UserRequestsRepository:
        return get_repository(self.app, UserRequestsRepository)

    @cached_property
    def runs_repo(self) -> RunsRepository:
        return get_repository(self.app, RunsRepository)

    @cached_property
    def steps_repo(self) -> StepsRepository:
        return get_repository(self.app, StepsRepository)

    async def add_start_workflow(self, node_id: NodeID) -> None:
        await _validate_workflow_creation_preconditions(
            node_id=node_id,
            runs_repo=self.runs_repo,
            user_requests_repo=self.user_requests_repo,
            payload_type=DynamicServiceStart,
        )
        created_run = await self.runs_repo.create_from_start_request(node_id)
        _logger.debug("Added %s workflow for '%s': %s", _START, node_id, created_run)

    async def add_stop_workflow(self, node_id: NodeID) -> None:
        await _validate_workflow_creation_preconditions(
            node_id=node_id,
            runs_repo=self.runs_repo,
            user_requests_repo=self.user_requests_repo,
            payload_type=DynamicServiceStop,
        )
        created_run = await self.runs_repo.create_from_stop_request(node_id)
        _logger.debug("Added %s workflow for '%s': %s", _STOP, node_id, created_run)

    async def cancel_workflow(self, node_id: NodeID) -> None:
        await _ensure_user_request(self.user_requests_repo, node_id)

        current_run = await self.runs_repo.get_run_from_node_id(node_id)
        if current_run is None:
            _logger.info("No active run to CANCEL found for '%s'", node_id)
            return

        await self.runs_repo.cancel_run(current_run.run_id)
        await self.steps_repo.mark_run_steps_as_skipped(self.app, current_run.run_id)
        _logger.debug("CANCELED workflow for '%s': %s", node_id, current_run)

    async def set_waiting_manual_intervention(self, node_id: NodeID) -> None:
        await _ensure_user_request(self.user_requests_repo, node_id)

        current_run = await _ensure_current_run(self.runs_repo, node_id)

        await self.runs_repo.set_waiting_manual_intervention(current_run.run_id)
        _logger.debug("Set waiting_manual_intervention for workflow of '%s': %s", node_id, current_run)

    async def complete_workflow(self, node_id: NodeID) -> None:
        """Cleanup after workflow finishes, by removing all DB entries related to the run"""
        current_run = await _ensure_current_run(self.runs_repo, node_id)

        await self.runs_repo.remove_run(current_run.run_id)

        _logger.debug("COMPLETED workflow for '%s': %s", node_id, current_run)

    async def _check_preconditions_skip_retry_step(self, node_id: NodeID, step_id: StepId) -> Step:
        # run check to see if workflow in appropriate state for step retry
        current_run = await self.runs_repo.get_run_from_node_id(node_id)
        if current_run is None:
            msg = f"No active run found for {node_id=}"
            raise RuntimeError(msg)

        if not current_run.waiting_manual_intervention:
            msg = f"Run {current_run.run_id=} is not waiting for manual intervention"
            raise RuntimeError(msg)

        # run checks to see if step can be retried
        step = await self.steps_repo.get_step_for_workflow_manager(step_id)
        if step is None:
            msg = f"No step found for step_id={step_id}"
            raise RuntimeError(msg)

        return step

    async def retry_workflow_step(self, node_id: NodeID, step_id: StepId) -> None:
        step = await self._check_preconditions_skip_retry_step(node_id, step_id)
        await self.steps_repo.manual_retry_step(step.step_id)

    async def skip_workflow_step(self, node_id: NodeID, step_id: StepId) -> None:
        await self._check_preconditions_skip_retry_step(node_id, step_id)

        await self.steps_repo.manual_skip_step(step_id)
