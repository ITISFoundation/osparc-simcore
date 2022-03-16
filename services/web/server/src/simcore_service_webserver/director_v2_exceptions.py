"""Defines the different exceptions that may arise in the director-v2 subpackage"""

from pydantic.errors import PydanticErrorMixin
from typing import Any


class DirectorServiceError(PydanticErrorMixin, RuntimeError):
    """Basic exception for errors raised by director-v2"""

    msg_template = "Unexpected error: director-v2 returned {status!r}, reason {reason!r} after calling {url!r}"

    def __init__(self, *, status: int, reason: str, **ctx: Any) -> None:
        self.status = status
        self.reason = reason
        super().__init__(status=status, reason=reason, **ctx)


class ClusterNotFoundError(DirectorServiceError):
    """Cluster was not found in director-v2"""

    msg_template = "Cluster {cluster_id!r} not found"


class ClusterAccessForbidden(DirectorServiceError):
    """Cluster access is forbidden"""

    msg_template = "Cluster {cluster_id!r} access forbidden!"
