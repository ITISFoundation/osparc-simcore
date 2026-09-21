"""Domain exceptions of the db_listener domain.

Pure leaf module: exception definitions only, no imports from any web-server
service/repository layer (see services/web/server/docs/DESIGN.md).
"""

from ..errors import WebServerBaseError

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
    """

    msg_template = "Failed to process outbox events of aggregate {kind}:{aggregate_id}"
