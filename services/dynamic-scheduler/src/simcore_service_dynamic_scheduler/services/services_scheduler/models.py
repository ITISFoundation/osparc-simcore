from dataclasses import dataclass
from datetime import datetime
from enum import auto
from typing import Any

from models_library.utils.enums import StrAutoEnum

type RunId = str
type StepId = str


class DbDesiredState(StrAutoEnum):
    PRESENT = auto()
    ABSENT = auto()


class DbRunKind(StrAutoEnum):
    APPLY = auto()
    TEARDOWN = auto()


class DbRunState(StrAutoEnum):
    APPLYING = auto()
    CANCEL_REQUESTED = auto()
    TEARING_DOWN = auto()
    SUCCEEDED = auto()


class DbDirection(StrAutoEnum):
    DO = auto()
    UNDO = auto()


class DbStepState(StrAutoEnum):
    PENDING = auto()
    RUNNING = auto()
    SUCCEEDED = auto()
    WAITING_MANUAL = auto()
    SKIPPED = auto()
    CANCELLED = auto()
    ABANDONED = auto()


class DbManualAction(StrAutoEnum):
    RETRY = auto()
    SKIP = auto()


@dataclass(frozen=True, slots=True)
class DagTemplate:
    workflow_id: str
    nodes: set[StepId]
    edges: set[tuple[StepId, StepId]]  # (depends_on, step)


@dataclass(frozen=True, slots=True)
class StepClaim:
    run_id: RunId
    step_id: StepId
    direction: DbDirection
    attempt: int
    worker_id: str
    lease_until: datetime


@dataclass(frozen=True, slots=True)
class WakeupMessage:
    run_id: RunId
    reason: str
    payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ManualAction:
    action: DbManualAction
    performed_by: str
    reason: str
