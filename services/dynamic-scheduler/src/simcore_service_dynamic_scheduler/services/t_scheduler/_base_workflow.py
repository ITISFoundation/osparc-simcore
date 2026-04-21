import asyncio
from abc import abstractmethod
from collections.abc import Callable, Coroutine
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from ._models import (
    ActivityCompleted,
    ActivityFailed,
    ActivityStarted,
    Compensation,
    CompensationCompleted,
    CompensationFailed,
    CompensationStarted,
    Decision,
    DecisionReceived,
    FailurePolicy,
    Parallel,
    ResolutionSignal,
    StateChanged,
    Step,
    StepSequence,
    WorkflowContext,
    WorkflowEventBase,
    WorkflowState,
)


class SagaWorkflow:  # pylint:disable=too-many-instance-attributes
    def __init__(self) -> None:
        self._state: WorkflowState = WorkflowState.RUNNING

        self._pending_decisions: dict[str, Decision] = {}
        self._awaiting_decisions: set[str] = set()

        self._running_activities: set[str] = set()
        self._compensations: list[Compensation] = []
        self._completed_activities: set[str] = set()
        self._failed_activities: dict[str, str] = {}
        self._compensated_activities: set[str] = set()
        self._failed_compensations: dict[str, str] = {}
        self._skipped_activities: set[str] = set()

        self._steps_total: int = 0
        self._history: list[dict[str, Any]] = []

    def _record(self, event: WorkflowEventBase) -> None:
        dumped = event.model_dump(mode="json")
        dumped["timestamp"] = workflow.now().isoformat()
        self._history.append(dumped)

    @abstractmethod
    def steps(self) -> StepSequence: ...

    @abstractmethod
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]: ...

    @classmethod
    def get_activities(cls) -> list[Callable[..., Coroutine[Any, Any, Any]]]:
        instance = cls.__new__(cls)
        activities: list[Callable[..., Coroutine[Any, Any, Any]]] = []
        for entry in instance.steps():
            steps = entry.steps if isinstance(entry, Parallel) else [entry]
            for step in steps:
                if step.fn not in activities:
                    activities.append(step.fn)
                if step.undo not in activities:
                    activities.append(step.undo)
        return activities

    @workflow.signal
    async def resolve(self, signal: ResolutionSignal) -> None:
        if signal.activity_name not in self._awaiting_decisions:
            workflow.logger.warning(
                "Ignoring signal for %r: not awaiting a decision (awaiting: %s)",
                signal.activity_name,
                self._awaiting_decisions,
            )
            return
        self._pending_decisions[signal.activity_name] = signal.decision

    @workflow.query
    def get_status(self) -> dict[str, Any]:
        # NOTE: sets are not JSON-serializable; sorted() ensures deterministic output across queries
        compensations_total = len(self._compensations)
        compensated_count = len(self._compensated_activities) + len(self._failed_compensations)
        return {
            "running_activities": sorted(self._running_activities),
            "completed_activities": sorted(self._completed_activities),
            "failed_activities": dict(self._failed_activities),
            "compensated_activities": sorted(self._compensated_activities),
            "failed_compensations": dict(self._failed_compensations),
            "skipped_activities": sorted(self._skipped_activities),
            "state": self._state,
            "steps_total": self._steps_total,
            "progress_percent": (
                (len(self._completed_activities) + len(self._skipped_activities)) / self._steps_total
                if self._steps_total > 0
                else 0.0
            ),
            "compensations_total": compensations_total,
            "compensation_progress": (compensated_count / compensations_total if compensations_total > 0 else 0.0),
        }

    @workflow.query
    def get_history(self) -> list[dict[str, str]]:
        return list(self._history)

    async def _run_saga(self, input_data: WorkflowContext) -> WorkflowContext:
        context: WorkflowContext = {**input_data}
        steps = self.steps()
        self._steps_total = sum(len(entry.steps) if isinstance(entry, Parallel) else 1 for entry in steps)

        try:
            await self._execute_steps(steps, context)
        except ActivityError:
            await self._compensate()
            self._state = WorkflowState.FAILED
            self._record(StateChanged(new_state=WorkflowState.FAILED))
            raise
        except asyncio.CancelledError:
            await self._compensate()
            self._state = WorkflowState.FAILED
            self._record(StateChanged(new_state=WorkflowState.FAILED))
            raise

        self._state = WorkflowState.COMPLETED
        self._record(StateChanged(new_state=WorkflowState.COMPLETED))
        return context

    async def _execute_steps(self, steps: StepSequence, context: dict[str, Any]) -> None:
        for step in steps:
            if isinstance(step, Parallel):
                results = await asyncio.gather(
                    *[self._run_one(s, context) for s in step.steps],
                    return_exceptions=True,
                )
                # Register compensations for steps that succeeded before re-raising
                first_error: BaseException | None = None
                for s, result in zip(step.steps, results, strict=True):
                    if isinstance(result, BaseException):
                        if first_error is None:
                            first_error = result
                        else:
                            workflow.logger.warning(
                                "Parallel activity %s also failed (first error will be raised): %s",
                                s.fn.__name__,
                                result,
                            )
                    elif result is not None:
                        context.update(result)
                        self._compensations.append(Compensation(activity=s.undo, input={**context}))
                        self._completed_activities.add(s.fn.__name__)
                if first_error is not None:
                    raise first_error
            else:
                result = await self._run_one(step, context)
                if result is not None:
                    context.update(result)
                    self._compensations.append(Compensation(activity=step.undo, input={**context}))
                    self._completed_activities.add(step.fn.__name__)

    async def _await_intervention(self, name: str, step: Step, context: dict[str, Any], err: ActivityError) -> Decision:
        self._running_activities.discard(name)
        self._state = WorkflowState.WAITING_INTERVENTION
        self._record(StateChanged(new_state=WorkflowState.WAITING_INTERVENTION))
        self._failed_activities[name] = f"{err}"
        self._awaiting_decisions.add(name)

        try:
            await workflow.wait_condition(lambda n=name: n in self._pending_decisions)  # type: ignore[misc]
        except asyncio.CancelledError:
            self._awaiting_decisions.discard(name)
            self._compensations.append(Compensation(activity=step.undo, input={**context}))
            raise

        decision = self._pending_decisions.pop(name)
        self._awaiting_decisions.discard(name)
        self._record(DecisionReceived(activity_name=name, decision=decision))

        if not self._awaiting_decisions:
            self._state = WorkflowState.RUNNING

        return decision

    async def _run_one(self, step: Step, context: dict[str, Any]) -> dict[str, Any] | None:
        name = step.fn.__name__
        self._running_activities.add(name)
        result: dict[str, Any] | None = None
        try:
            while True:
                self._record(ActivityStarted(activity_name=name))
                try:
                    result = await workflow.execute_activity(
                        step.fn,
                        context,
                        start_to_close_timeout=step.timeout,
                        retry_policy=step.retry,
                        heartbeat_timeout=step.heartbeat_timeout,
                    )
                except ActivityError as err:
                    self._record(ActivityFailed(activity_name=name, error=f"{err}"))
                    match step.on_failure:
                        case FailurePolicy.ROLLBACK:
                            self._failed_activities[name] = f"{err}"
                            self._compensations.append(Compensation(activity=step.undo, input={**context}))
                            raise

                        case FailurePolicy.MANUAL_INTERVENTION:
                            decision = await self._await_intervention(name, step, context, err)
                            match decision:
                                case Decision.RETRY:
                                    del self._failed_activities[name]
                                    self._running_activities.add(name)
                                    continue
                                case Decision.SKIP:
                                    del self._failed_activities[name]
                                    self._skipped_activities.add(name)
                                    return None
                                case Decision.ROLLBACK:
                                    self._compensations.append(Compensation(activity=step.undo, input={**context}))
                                    raise
                else:
                    self._record(ActivityCompleted(activity_name=name))
                    return result
        finally:
            self._running_activities.discard(name)

    async def _compensate(self) -> None:
        self._state = WorkflowState.COMPENSATING
        self._record(StateChanged(new_state=WorkflowState.COMPENSATING))
        for comp in reversed(self._compensations):
            comp_name = f"compensate:{comp.activity.__name__}"
            self._running_activities.add(comp_name)
            self._record(CompensationStarted(activity_name=comp.activity.__name__))
            try:
                await workflow.execute_activity(
                    comp.activity,
                    comp.input,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                self._compensated_activities.add(comp.activity.__name__)
                self._record(CompensationCompleted(activity_name=comp.activity.__name__))
            except ActivityError as err:
                self._failed_compensations[comp.activity.__name__] = f"{err}"
                self._record(CompensationFailed(activity_name=comp.activity.__name__, error=f"{err}"))
                workflow.logger.error(
                    "Compensation %s failed, continuing with remaining",
                    comp.activity.__name__,
                )
            finally:
                self._running_activities.discard(comp_name)
