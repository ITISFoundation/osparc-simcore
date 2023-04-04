"""Defines the different exceptions that may arise in the director-v2 subpackage"""

from typing import Any

from pydantic.errors import PydanticErrorMixin


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


class ClusterPingError(DirectorServiceError):
    """Cluster ping failed"""

    msg_template = "Connection to cluster in {endpoint!r} failed, received {reason!r}"


class ClusterDefinedPingError(DirectorServiceError):
    """Cluster ping failed"""

    msg_template = "Connection to cluster {cluster_id!r} failed, received {reason!r}"


class ServiceWaitingForManualIntervention(DirectorServiceError):
    msg_template = "Service {service_uuid} is waiting for user manual intervention"
