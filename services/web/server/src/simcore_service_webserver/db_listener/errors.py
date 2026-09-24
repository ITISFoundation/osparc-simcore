"""Domain exceptions of the db_listener domain.

Pure leaf module: exception definitions only, no imports from any web-server
service/repository layer (see services/web/server/docs/DESIGN.md).
"""

from ..errors import WebServerBaseError
from .models import AggregateID, AggregateType, OutboxEventID

__all__ = ("CompTaskNotFoundError", "DbListenerBaseError", "OutboxProcessingError")


class DbListenerBaseError(WebServerBaseError): ...


class CompTaskNotFoundError(DbListenerBaseError):
    """The comp_tasks row an outbox event points at is gone (deleted task/project)"""

    msg_template = "Comp task {task_id} not found"


class OutboxProcessingError(DbListenerBaseError):
    """Projection of a claimed outbox aggregate failed.

    Raised to abort the claim transaction; carries the context needed to record
    the failed attempt once the transaction has rolled back (the claim's locks
    released and pending delete undone).

    The attributes are provided as keyword context to OsparcErrorMixin.__init__
    (which stores them in the instance dict); the annotations below only declare
    them for static type-checkers.
    """

    kind: AggregateType
    aggregate_id: AggregateID
    event_ids: list[OutboxEventID]
    cause: Exception

    msg_template = "Failed to process outbox events of aggregate {kind}:{aggregate_id}"
