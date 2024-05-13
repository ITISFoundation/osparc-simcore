"""Defines the different exceptions that may arise in the director-v2 subpackage"""

from typing import Any

from ..errors import WebServerBaseError


class DirectorServiceError(WebServerBaseError, RuntimeError):
    """Basic exception for errors raised by director-v2"""

    msg_template = "Unexpected error: director-v2 returned '{status}', reason '{reason}' after calling '{url}'"

    def __init__(self, *, status: int, reason: str, **ctx: Any) -> None:
        super().__init__(**ctx)
        self.status = status
        self.reason = reason


class ComputationNotFoundError(DirectorServiceError):
    msg_template = "Computation '{project_id}' not found"


class ClusterNotFoundError(DirectorServiceError):
    """Cluster was not found in director-v2"""

    msg_template = "Cluster '{cluster_id}' not found"


class ClusterAccessForbidden(DirectorServiceError):
    """Cluster access is forbidden"""

    msg_template = "Cluster '{cluster_id}' access forbidden!"


class ClusterPingError(DirectorServiceError):
    """Cluster ping failed"""

    msg_template = "Connection to cluster in '{endpoint}' failed, received '{reason}'"


class ClusterDefinedPingError(DirectorServiceError):
    """Cluster ping failed"""

    msg_template = "Connection to cluster '{cluster_id}' failed, received '{reason}'"


class ServiceWaitingForManualIntervention(DirectorServiceError):
    msg_template = "Service '{service_uuid}' is waiting for user manual intervention"
