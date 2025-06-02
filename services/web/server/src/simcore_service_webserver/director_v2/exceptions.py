"""Defines the different exceptions that may arise in the director-v2 subpackage"""

from typing import Any

from ..errors import WebServerBaseError


class DirectorV2ServiceError(WebServerBaseError, RuntimeError):
    """Basic exception for errors raised by director-v2"""

    msg_template = "Unexpected error: director-v2 returned '{status}', reason '{reason}' after calling '{url}'"

    def __init__(self, *, status: int, reason: str, **ctx: Any) -> None:
        super().__init__(**ctx)
        self.status = status
        self.reason = reason


class ComputationNotFoundError(DirectorV2ServiceError):
    msg_template = "Computation '{project_id}' not found"
