from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import auto
from typing import TYPE_CHECKING, Any

from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.utils.enums import StrAutoEnum

if TYPE_CHECKING:
    from ._abc import BaseStep

type InData = dict[str, Any]
type OutData = dict[str, Any] | None


@dataclass(frozen=True)
class KeyConfig:
    name: str = field(metadata={"description": "Name of the key"})
    optional: bool = field(default=False, metadata={"description": "if True the key can be omitted"})


type InDataKeys = set[KeyConfig]
type OutDataKeys = set[KeyConfig]


@dataclass
class WorkflowDefinition:
    initial_context: set[KeyConfig]
    steps: list[tuple[type["BaseStep"], list[type["BaseStep"]]]]


type WorkflowName = str
type DagNodeUniqueReference = str
type StepSequence = tuple[set[DagNodeUniqueReference], ...]


class SchedulerServiceStatus(StrAutoEnum):
    IDLE = auto()
    RUNNING = auto()
    FAILED = auto()


@dataclass
class DagStepSequences:
    apply: StepSequence
    revert: StepSequence


type WorkerId = str
type StepId = int
type RunId = int


class ServiceRequested(StrAutoEnum):
    PRESENT = auto()
    ABSENT = auto()


class StepState(StrAutoEnum):
    CREATED = auto()
    READY = auto()
    RUNNING = auto()

    FAILED = auto()
    SKIPPED = auto()
    SUCCESS = auto()
    CANCELLED = auto()


@dataclass
class UserRequest:
    node_id: NodeID
    product_name: ProductName

    requested_at: datetime
    service_requested: ServiceRequested
    payload: DynamicServiceStart | DynamicServiceStop


@dataclass
class Run:
    run_id: RunId
    created_at: datetime

    node_id: NodeID
    workflow_name: WorkflowName

    is_rolling_back: bool
    waiting_manual_intervention: bool


@dataclass
class RunStore:
    # primary key is run_id + key
    run_id: RunId
    updated_at: datetime

    key: str
    value: Any


@dataclass
class Step:  # pylint: disable=too-many-instance-attributes
    step_id: StepId
    created_at: datetime

    run_id: RunId
    step_type: DagNodeUniqueReference

    finished_at: datetime | None
    available_attempts: int
    attempt_number: int
    timeout: timedelta
    state: StepState
    message: str | None


@dataclass
class StepLease:
    step_id: StepId

    renew_count: int
    owner: WorkerId

    acquired_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime


@dataclass
class StepHistory:
    step_id: StepId

    attempt: int
    state: StepState
    finished_at: datetime
    message: str
