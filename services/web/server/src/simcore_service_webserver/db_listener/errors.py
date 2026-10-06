"""Domain exceptions of the db_listener domain.

Pure leaf module: exception definitions only, no imports from any web-server
service/repository layer (see services/web/server/docs/DESIGN.md).
"""

from ..errors import WebServerBaseError

__all__ = ("CompTaskNotFoundError", "DbListenerBaseError")


class DbListenerBaseError(WebServerBaseError): ...


class CompTaskNotFoundError(DbListenerBaseError):
    """The comp_tasks row an outbox event points at is gone (deleted task/project)"""

    msg_template = "Comp task {task_id} not found"
