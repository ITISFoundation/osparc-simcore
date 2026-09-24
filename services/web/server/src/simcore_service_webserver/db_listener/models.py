"""Public domain models of the db_listener domain.

Pure leaf module: type definitions only, no imports from any web-server
service/repository layer (see services/web/server/docs/DESIGN.md).
"""

from typing import Any, Final, NewType

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel, ConfigDict

# consumer's meaning of an event's changed_columns: a change to any of these
# comp_tasks columns must refresh the node's outputs projection / its running
# state (the values must match the columns watched by the trigger defined in
# simcore_postgres_database/models/comp_tasks.py)
DB_OUTBOX_CHANGED_COLUMNS_OUTPUTS: Final[frozenset[str]] = frozenset({"outputs", "run_hash"})
DB_OUTBOX_CHANGED_COLUMN_STATE: Final[str] = "state"

# identity types of the outbox_events table columns (see models/outbox_events.py)
OutboxEventID = NewType("OutboxEventID", int)
AggregateType = NewType("AggregateType", str)
AggregateID = NewType("AggregateID", str)

__all__ = (
    "DB_OUTBOX_CHANGED_COLUMNS_OUTPUTS",
    "DB_OUTBOX_CHANGED_COLUMN_STATE",
    "AggregateID",
    "AggregateType",
    "ClaimOutcome",
    "ClaimableAggregate",
    "ClaimedAggregate",
    "CompTask",
    "FailedAttempt",
    "OutboxEventID",
)


class _BaseFrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, slots=True)


class ClaimOutcome(_BaseFrozenModel):
    """Result of one claim-and-process iteration of the outbox drain."""

    success: bool
    kind: AggregateType
    aggregate_id: AggregateID
    # only meaningful when not success; see _service._INFRA_EXCEPTION_TYPES
    is_infra_error: bool = False


class ClaimableAggregate(_BaseFrozenModel):
    """Aggregate with at least one claimable outbox event, as listed by a candidate scan."""

    kind: AggregateType
    aggregate_id: AggregateID


class ClaimedAggregate(ClaimableAggregate):
    """All outbox events a single claim won for one aggregate."""

    event_ids: list[OutboxEventID]
    # union of the changed_columns of all co-claimed events
    changed_columns: frozenset[str]


class CompTask(_BaseFrozenModel):
    """Current comp_tasks row as needed by the projects_nodes projection."""

    task_id: int
    project_id: ProjectID
    node_id: NodeID
    outputs: dict[str, Any] | None
    run_hash: str | None
    state: str | None


class FailedAttempt(_BaseFrozenModel):
    """One outbox event whose processing attempt was just recorded as failed."""

    event_id: OutboxEventID
    kind: AggregateType
    aggregate_id: AggregateID
    attempts: int
