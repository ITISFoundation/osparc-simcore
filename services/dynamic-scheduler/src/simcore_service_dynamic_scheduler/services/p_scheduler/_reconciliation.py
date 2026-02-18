import logging
import time
from asyncio import QueueFull, Task, create_task
from datetime import timedelta
from functools import cached_property
from typing import Final

from common_library.async_tools import cancel_wait_task
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeInt
from servicelib.background_task_utils import exclusive_periodic
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context
from settings_library.redis import RedisDatabase

from ..base_repository import get_repository
from ..redis import get_redis_client
from ._lifecycle_protocol import SupportsLifecycle
from ._metrics import PSchedulerMetrics
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
from ._notifications import RK_RECONSILIATION, NotificationsManager
from ._queue import BoundedPubSubQueue, get_consumer_count
from ._repositories import RunsRepository, StepsRepository, UserRequestsRepository
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
                    await workflow_manager.add_start_workflow(node_id)
                case SchedulerServiceStatus.IS_PRESENT:
                    requires_forther_actions = False
                case SchedulerServiceStatus.IN_ERROR:
                    await workflow_manager.add_stop_workflow(node_id)
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
                    await workflow_manager.add_stop_workflow(node_id)
                case SchedulerServiceStatus.IN_ERROR:
                    await workflow_manager.add_stop_workflow(node_id)
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
    returns True if action was taken that prevents further processing of the workflow in this iteration
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


async def _reconciliate(app: FastAPI, *, node_id: NodeID) -> None:
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


_NAME: Final[str] = "scheduler_reconciliation_manager"


class ReconciliationManager(SingletonInAppStateMixin, SupportsLifecycle):
    app_state_name: str = f"p_{_NAME}"

    def __init__(
        self,
        app: FastAPI,
        *,
        periodic_checks_interval: timedelta,
        queue_consumer_expected_runtime_duration: timedelta,
        queue_max_burst: NonNegativeInt,
    ) -> None:
        self.app = app
        self.periodic_checks_interval = periodic_checks_interval

        self._consumer_count = get_consumer_count(queue_consumer_expected_runtime_duration, queue_max_burst)
        _logger.info("reconciliation queue consumers count=%s", self._consumer_count)
        self._queue: BoundedPubSubQueue[NodeID] = BoundedPubSubQueue(maxsize=self._consumer_count)

        self._task_periodic_checks: Task | None = None

    @cached_property
    def _notifications_manager(self) -> NotificationsManager:
        return NotificationsManager.get_from_app_state(self.app)

    @cached_property
    def _runs_repo(self) -> RunsRepository:
        return get_repository(self.app, RunsRepository)

    @cached_property
    def _metrics_manager(self) -> PSchedulerMetrics:
        return PSchedulerMetrics.get_from_app_state(self.app)

    async def _push_to_queue(self, node_id: NodeID) -> None:
        try:
            await self._queue.put(node_id)
        except QueueFull:
            self._metrics_manager.inc_dropped_reconciliation_requests()
            _logger.warning("reconciliation queue is full, dropping request for node_id=%s", node_id)

    async def _handle_reconciliation_notification(self, message: NodeID) -> None:
        await self._push_to_queue(message)

    async def _unique_worker_periodic_checks(self) -> None:
        """
        This setup will only be done if a lock is acquired,
        Only one instance globally will handle the reconciliation.
        """
        tracked_runs = await self._runs_repo.get_all_runs()
        with log_context(_logger, logging.DEBUG, "requesting checks for %s tracked runs", len(tracked_runs)):
            for run in tracked_runs:
                await self._notifications_manager.send_riconciliation_event(run.node_id)

    async def _safe_reconciliate(self, node_id: NodeID) -> None:
        with log_context(_logger, logging.DEBUG, "reconciliation node_id='%s'", node_id):
            try:
                start = time.perf_counter()
                await _reconciliate(self.app, node_id=node_id)
                elapsed = time.perf_counter() - start

                self._metrics_manager.duration_of_reconciliation(elapsed)
                _logger.debug("reconciliation for node_id=%s took %.2f seconds", node_id, elapsed)
            except Exception:
                self._metrics_manager.inc_reconciliation_failures()
                raise

    async def setup(self) -> None:
        for _ in range(self._consumer_count):
            self._queue.subscribe(self._safe_reconciliate)

        self._notifications_manager.subscribe_handler(
            routing_key=RK_RECONSILIATION, handler=self._handle_reconciliation_notification
        )

        @exclusive_periodic(
            get_redis_client(self.app, RedisDatabase.LOCKS),
            task_interval=self.periodic_checks_interval,
            retry_after=self.periodic_checks_interval,
        )
        async def _periodic_unique_worker_periodic_checks() -> None:
            await self._unique_worker_periodic_checks()

        self._task_periodic_checks = create_task(_periodic_unique_worker_periodic_checks(), name=f"periodic_{_NAME}")

    async def shutdown(self) -> None:
        if self._task_periodic_checks is not None:
            await cancel_wait_task(self._task_periodic_checks)

        await self._queue.close()
