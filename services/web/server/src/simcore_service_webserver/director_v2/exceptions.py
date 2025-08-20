"""Defines the different exceptions that may arise in the director-v2 subpackage"""

from typing import Any

from ..errors import WebServerBaseError


class DirectorV2ServiceError(WebServerBaseError, RuntimeError):
    """Basic exception for errors raised by director-v2"""

    msg_template = "Unexpected error: director-v2 returned '{status}', details '{details}' after calling '{url}'"

    def __init__(self, *, status: int, details: str, **ctx: Any) -> None:
        super().__init__(**ctx)
        self.status = status
        self.details = details


class ComputationNotFoundError(DirectorV2ServiceError):
    msg_template = "Computation '{project_id}' not found"
