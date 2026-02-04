import logging
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ..base_repository import get_repository
from ._models import (
    DagNodeUniqueReference,
    Run,
    SchedulerServiceStatus,
    Step,
    StepsSequence,
    StepState,
    UserDesiredState,
    UserRequest,
)
from ._node_status import StatusManager
from ._notifications import NotificationsManager
from ._repositories.runs import RunsRepository
from ._repositories.steps import StepsRepository
from ._repositories.user_requests import UserRequestsRepository
from ._workflow_manager import WorkflowManager
from ._workflow_registry import WorkflowRegistry

_logger = logging.getLogger(__name__)

_FINAL_STEP_STATES: Final[set[StepState]] = {StepState.SUCCESS, StepState.SKIPPED, StepState.CANCELLED}


class UnexpectedRecociliationError(Exception): ...


async def _enforce_service_presence(  # noqa: C901
    workflow_manager: WorkflowManager,
    node_id: NodeID,
    user_request: UserRequest,
    scheduler_service_status: SchedulerServiceStatus,
) -> bool:
    """
    Enforces that the service presence matches the user request.
    returns True if further actions are required to reach the desired state
    """
    requires_forther_actions: bool = True

    match user_request.user_desired_state:
        case UserDesiredState.PRESENT:
            match scheduler_service_status:
                case SchedulerServiceStatus.IS_ABSENT:
                    await workflow_manager.start_workflow(node_id)
                case SchedulerServiceStatus.IS_PRESENT:
                    requires_forther_actions = False
                case SchedulerServiceStatus.IN_ERROR:
                    await workflow_manager.stop_workflow(node_id)
                case SchedulerServiceStatus.TRANSITION_TO_PRESENT:
                    requires_forther_actions = False
                case SchedulerServiceStatus.TRANSITION_TO_ABSENT:
                    # stop cannot be cancelled need to wait uniil it finishes
                    requires_forther_actions = False

        case UserDesiredState.ABSENT:
            match scheduler_service_status:
                case SchedulerServiceStatus.IS_ABSENT:
                    requires_forther_actions = False
                case SchedulerServiceStatus.IS_PRESENT:
                    await workflow_manager.stop_workflow(node_id)
                case SchedulerServiceStatus.IN_ERROR:
                    await workflow_manager.stop_workflow(node_id)
                case SchedulerServiceStatus.TRANSITION_TO_PRESENT:
                    await workflow_manager.cancel_workflow(node_id)
                case SchedulerServiceStatus.TRANSITION_TO_ABSENT:
                    requires_forther_actions = False

    return requires_forther_actions


async def _create_steps_if_missing(
    steps_repo: StepsRepository, workflow_registry: WorkflowRegistry, steps_sequence: StepsSequence, current_run: Run
) -> None:
    """adds missing steps either for APPLY or REVERT"""
    steps_references = await steps_repo.get_all_run_tracked_steps(current_run.run_id)

    for step_sequence in steps_sequence:
        for step_type in step_sequence:
            step_class = workflow_registry.get_base_step(step_type)
            if (step_type, current_run.is_reverting) not in steps_references:
                await steps_repo.create_step(
                    run_id=current_run.run_id,
                    step_type=step_type,
                    step_class=step_class,
                    is_reverting=current_run.is_reverting,
                )


async def _if_any_reschedule_failed_steps_or_give_up(
    workflow_manager: WorkflowManager,
    notifications_manager: NotificationsManager,
    steps_repo: StepsRepository,
    run_steps: dict[tuple[DagNodeUniqueReference, bool], Step],
    node_id: NodeID,
    current_run: Run,
) -> bool:
    """tries to reschedule failed steps.
    if no retries are left either cancels the workflow or sets it to wait for manual intervention
    returns True if action was taken that prevents further processing of the workflow in this loop iteration
    """
    for step in run_steps.values():
        if step.state == StepState.FAILED:
            if step.available_attempts <= 0:
                if not current_run.is_reverting:
                    await workflow_manager.cancel_workflow(node_id)
                    await notifications_manager.send_riconciliation_event(node_id)
                else:
                    await workflow_manager.set_waiting_manual_intervention(node_id)
                    _logger.info(
                        "workflow '%s' for node_id='%s:' waiting for manual intervention",
                        current_run.workflow_name,
                        node_id,
                    )
                # in both cases we do nothing else
                return True

            await steps_repo.retry_failed_step(step.step_id)

    return False


async def _set_created_steps_as_ready(
    app: FastAPI,
    steps_repo: StepsRepository,
    current_run: Run,
    steps_sequence: StepsSequence,
    run_steps: dict[tuple[DagNodeUniqueReference, bool], Step],
):
    """sets as READY all steps that are in CREATED state, following the steps sequence order"""
    all_steps_ready: bool = True
    for step_sequence in steps_sequence:
        for step_type in step_sequence:
            step = run_steps[(step_type, current_run.is_reverting)]

            if step.state not in {StepState.SUCCESS, StepState.SKIPPED}:
                all_steps_ready = False

            if step.state == StepState.CREATED:
                await steps_repo.set_step_as_ready(app, step.step_id)

        if not all_steps_ready:
            # stop here, do not schedule more
            break


async def _cleanup_run_if_completed(
    node_id: NodeID, workflow_manager: WorkflowManager, steps_repo: StepsRepository, current_run: Run
):
    """checks if all steps are completed, and if so cleans up the run"""
    run_steps = await steps_repo.get_all_run_tracked_steps_states(current_run.run_id)
    for step in run_steps.values():
        if step.state not in _FINAL_STEP_STATES:
            return

    await workflow_manager.complete_workflow(node_id)
    _logger.info("workflow '%s' for node_id='%s:' completed successfully", current_run.workflow_name, node_id)


async def loop(app: FastAPI, node_id: NodeID) -> None:
    status_manager = StatusManager.get_from_app_state(app)
    workflow_registry = WorkflowRegistry.get_from_app_state(app)
    workflow_manager = WorkflowManager.get_from_app_state(app)
    notifications_manager = NotificationsManager.get_from_app_state(app)

    user_requests_repo = get_repository(app, UserRequestsRepository)
    runs_repo = get_repository(app, RunsRepository)
    steps_repo = get_repository(app, StepsRepository)

    # 1. ENFORCE WORKFLOWS
    scheduler_service_status = await status_manager.get_scheduler_service_status(node_id)
    user_request = await user_requests_repo.get_user_request(node_id)

    if user_request is None:
        msg = f"No user request found for node_id={node_id} not found"
        raise UnexpectedRecociliationError(msg)

    requires_further_actions = await _enforce_service_presence(
        workflow_manager, node_id, user_request, scheduler_service_status
    )
    if requires_further_actions is False:
        return None

    # 2. MATERIALISE STEPS IN DB IF MISSING
    current_run = await runs_repo.get_run_from_node_id(node_id)

    if current_run is None:
        msg = f"No run found for node_id={node_id} not found"
        raise UnexpectedRecociliationError(msg)

    if current_run.waiting_manual_intervention:
        _logger.debug("waiting for manual intervention to proceed for %s", node_id)
        return None

    steps_sequence = workflow_registry.get_workflow_steps_sequence(current_run.workflow_name)

    await _create_steps_if_missing(steps_repo, workflow_registry, steps_sequence, current_run)

    # 3. INSPECT STEPS AND DECIDE WHAT TO DO NEXT
    run_steps = await steps_repo.get_all_run_tracked_steps_states(current_run.run_id)

    if await _if_any_reschedule_failed_steps_or_give_up(
        workflow_manager, notifications_manager, steps_repo, run_steps, node_id, current_run
    ):
        return None

    await _set_created_steps_as_ready(app, steps_repo, current_run, steps_sequence, run_steps)

    # 4. CLEANUP RUN IF COMPLETED
    return await _cleanup_run_if_completed(node_id, workflow_manager, steps_repo, current_run)
