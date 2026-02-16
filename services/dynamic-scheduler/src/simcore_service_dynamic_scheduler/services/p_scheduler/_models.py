from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import auto
from typing import TYPE_CHECKING, Any

from models_library.api_schemas_dynamic_scheduler.dynamic_services import DynamicServiceStart, DynamicServiceStop
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
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
type StepsSequence = tuple[set[DagNodeUniqueReference], ...]


class SchedulerServiceStatus(StrAutoEnum):
    IS_ABSENT = auto()  # not running
    IS_PRESENT = auto()  # running without issues
    IN_ERROR = auto()  # in error state
    TRANSITION_TO_PRESENT = auto()  # transitioning to running
    TRANSITION_TO_ABSENT = auto()  # transitioning to not running


type WorkerId = str
type StepId = int
type RunId = int


class UserDesiredState(StrAutoEnum):
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
    product_name: ProductName
    user_id: UserID
    project_id: ProjectID
    node_id: NodeID

    requested_at: datetime
    user_desired_state: UserDesiredState
    payload: DynamicServiceStart | DynamicServiceStop


@dataclass
class Run:
    run_id: RunId
    created_at: datetime

    node_id: NodeID
    workflow_name: WorkflowName

    is_reverting: bool
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

    # 3 fields for primary key
    run_id: RunId
    step_type: DagNodeUniqueReference
    is_reverting: bool

    timeout: timedelta

    available_attempts: int
    attempt_number: int

    state: StepState
    finished_at: datetime | None
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
class StepFailHistory:
    step_id: StepId

    attempt: int
    state: StepState
    finished_at: datetime
    message: str
