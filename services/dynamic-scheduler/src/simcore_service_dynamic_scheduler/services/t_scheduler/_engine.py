from typing import Any

from fastapi import FastAPI
from pydantic import TypeAdapter
from temporalio.client import WorkflowHandle
from temporalio.common import WorkflowIDConflictPolicy

from ...core.settings import ApplicationSettings
from ._dependencies import get_temporalio_client, get_workflow_registry
from ._errors import ActivityNotInFailedError
from ._models import (
    Decision,
    ResolutionSignal,
    RunningWorkflowInfo,
    WorkflowContext,
    WorkflowEvent,
    WorkflowHistory,
    WorkflowId,
    WorkflowState,
    WorkflowStatus,
)


class WorkflowEngine:
    """Public API for managing Temporalio saga workflows."""

    def __init__(self, app: FastAPI) -> None:
        settings: ApplicationSettings = app.state.settings
        self._client = get_temporalio_client(app)
        self._task_queue = settings.DYNAMIC_SCHEDULER_TEMPORALIO_SETTINGS.TEMPORALIO_TASK_QUEUE
        self._registry = get_workflow_registry(app)

    async def start(
        self,
        workflow_name: str,
        *,
        workflow_id: WorkflowId,
        context: WorkflowContext,
    ) -> None:
        """Start a new workflow execution.

        Args:
            workflow_name: Registry key matching a ``@workflow.defn`` class
                previously registered via ``WorkflowRegistry``.
            workflow_id: Unique identifier for this execution.  Must not
                collide with an already-running workflow.
            context: Arbitrary dict forwarded to every activity as its
                first argument.

        Raises:
            WorkflowNotFoundError: If *workflow_name* is not in the registry.
            temporalio.service.RPCError: If a workflow with the same
                *workflow_id* is already running.
        """
        workflow_cls = self._registry.get_workflow(workflow_name)
        await self._client.start_workflow(
            workflow_cls.run,
            context,
            id=workflow_id,
            task_queue=self._task_queue,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )

    async def cancel(self, workflow_id: WorkflowId) -> None:
        """Request cancellation of a running workflow.

        The workflow will enter its compensation phase, undoing completed
        steps in reverse order.
        """
        handle: WorkflowHandle = self._client.get_workflow_handle(workflow_id)
        await handle.cancel()

    async def status(self, workflow_id: WorkflowId) -> WorkflowStatus:
        """Query the current status of a workflow.

        Returns a ``WorkflowStatus`` snapshot including the current state,
        which activities are running / completed / failed / compensated,
        and overall progress (0-1).
        """
        handle: WorkflowHandle = self._client.get_workflow_handle(workflow_id)
        raw: dict[str, Any] = await handle.query("get_status")
        return WorkflowStatus(
            state=WorkflowState(raw["state"]),
            running_activities=set(raw["running_activities"]),
            completed_activities=set(raw["completed_activities"]),
            failed_activities=raw["failed_activities"],
            compensated_activities=set(raw["compensated_activities"]),
            failed_compensations=raw["failed_compensations"],
            skipped_activities=set(raw["skipped_activities"]),
            steps_total=raw["steps_total"],
            progress_percent=raw["progress_percent"],
            compensations_total=raw["compensations_total"],
            compensation_progress=raw["compensation_progress"],
        )

    async def history(self, workflow_id: WorkflowId) -> WorkflowHistory:
        handle: WorkflowHandle = self._client.get_workflow_handle(workflow_id)
        raw: list[dict[str, Any]] = await handle.query("get_history")
        return WorkflowHistory(events=[TypeAdapter(WorkflowEvent).validate_python(e) for e in raw])

    async def signal(self, workflow_id: WorkflowId, *, activity_name: str, decision: Decision) -> None:
        """Resolve a failed activity that is awaiting manual intervention.

        Only meaningful when the workflow is in ``WAITING_INTERVENTION``
        state.  Each failed activity in a parallel group must be resolved
        individually.

        Args:
            workflow_id: Target workflow.
            activity_name: Name of the failed activity to resolve
                (must match a key in ``WorkflowStatus.failed_activities``).
            decision: Action to take — ``RETRY`` to re-execute,
                ``SKIP`` to ignore the failure and continue, or
                ``ROLLBACK`` to trigger compensation.

        Raises:
            ActivityNotInFailedError: If *activity_name* is not in the
                workflow's failed activities.
        """
        status = await self.status(workflow_id)
        if activity_name not in status.failed_activities:
            raise ActivityNotInFailedError(
                activity_name=activity_name,
                workflow_id=workflow_id,
                failed=set(status.failed_activities.keys()),
            )
        handle: WorkflowHandle = self._client.get_workflow_handle(workflow_id)
        await handle.signal("resolve", ResolutionSignal(activity_name=activity_name, decision=decision))

    async def list_running_workflows(self) -> list["RunningWorkflowInfo"]:
        """List all workflows currently running on this service's task queue."""
        query = f"TaskQueue = '{self._task_queue}' AND ExecutionStatus = 'Running'"
        return [
            RunningWorkflowInfo(workflow_id=wf.id, workflow_type=wf.workflow_type)
            async for wf in self._client.list_workflows(query)
        ]

    async def cancel_all_workflows(self) -> int:
        """Cancel every running workflow, triggering saga compensation.

        Used by ops before deploying a new version that changes
        workflow structure or activity implementations.
        """
        running = await self.list_running_workflows()
        for wf in running:
            handle: WorkflowHandle = self._client.get_workflow_handle(wf.workflow_id)
            await handle.cancel()
        return len(running)
