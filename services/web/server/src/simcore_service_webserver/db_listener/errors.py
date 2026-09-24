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

    Pure control-flow marker: raised to abort (roll back) the claim transaction, so
    its advisory and row locks are released and the pending delete undone. The
    aggregate context is message-only -- the failed claim stays in the raiser's
    scope and the underlying error arrives chained (`raise ... from`).
    """

    msg_template = "Failed to process outbox events of aggregate {kind}:{aggregate_id}"
