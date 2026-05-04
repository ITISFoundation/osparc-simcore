from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import auto
from typing import Annotated, Any, Literal

from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, Field
from temporalio.common import RetryPolicy

type WorkflowId = str
type WorkflowContext = dict[str, Any]


class FailurePolicy(StrAutoEnum):
    ROLLBACK = auto()
    MANUAL_INTERVENTION = auto()


class Decision(StrAutoEnum):
    RETRY = auto()
    SKIP = auto()
    ROLLBACK = auto()


class WorkflowState(StrAutoEnum):
    RUNNING = auto()
    COMPENSATING = auto()
    WAITING_INTERVENTION = auto()
    COMPLETED = auto()
    FAILED = auto()


# --- Workflow Event hierarchy (Pydantic discriminated union) ---


class WorkflowEventBase(BaseModel):
    timestamp: datetime | None = None


class ActivityStarted(WorkflowEventBase):
    kind: Literal["activity_started"] = "activity_started"
    activity_name: str


class ActivityCompleted(WorkflowEventBase):
    kind: Literal["activity_completed"] = "activity_completed"
    activity_name: str


class ActivityFailed(WorkflowEventBase):
    kind: Literal["activity_failed"] = "activity_failed"
    activity_name: str
    error: str = ""


class CompensationStarted(WorkflowEventBase):
    kind: Literal["compensation_started"] = "compensation_started"
    activity_name: str


class CompensationCompleted(WorkflowEventBase):
    kind: Literal["compensation_completed"] = "compensation_completed"
    activity_name: str


class CompensationFailed(WorkflowEventBase):
    kind: Literal["compensation_failed"] = "compensation_failed"
    activity_name: str
    error: str = ""


class DecisionReceived(WorkflowEventBase):
    kind: Literal["decision_received"] = "decision_received"
    activity_name: str
    decision: Decision


class StateChanged(WorkflowEventBase):
    kind: Literal["state_changed"] = "state_changed"
    new_state: WorkflowState


AnyWorkflowEvent = (
    ActivityStarted
    | ActivityCompleted
    | ActivityFailed
    | CompensationStarted
    | CompensationCompleted
    | CompensationFailed
    | DecisionReceived
    | StateChanged
)

WorkflowEvent = Annotated[AnyWorkflowEvent, Field(discriminator="kind")]


@dataclass(frozen=True)
class Step:
    fn: Callable[..., Coroutine[Any, Any, Any]]
    undo: Callable[..., Coroutine[Any, Any, None]]
    retry: RetryPolicy = field(
        default_factory=lambda: RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=2))
    )
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=60))
    on_failure: FailurePolicy = FailurePolicy.ROLLBACK
    heartbeat_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))


@dataclass(frozen=True)
class Parallel:
    steps: list[Step]


def parallel(*steps: Step) -> Parallel:
    return Parallel(steps=list(steps))


type StepSequence = tuple[Step | Parallel, ...]


@dataclass
class Compensation:
    activity: Callable[..., Coroutine[Any, Any, None]]
    input: Any


@dataclass(frozen=True)
class WorkflowStatus:  # pylint:disable=too-many-instance-attributes
    state: WorkflowState
    running_activities: set[str]
    completed_activities: set[str]
    failed_activities: dict[str, str]
    compensated_activities: set[str]
    failed_compensations: dict[str, str]
    skipped_activities: set[str]
    steps_total: int
    progress_percent: float
    compensations_total: int
    compensation_progress: float


@dataclass(frozen=True)
class WorkflowHistory:
    events: list[AnyWorkflowEvent]


@dataclass(frozen=True)
class ResolutionSignal:
    activity_name: str
    decision: Decision


class RunningWorkflowInfo(BaseModel):
    workflow_id: str
    workflow_type: str
