""" Defines the different exceptions that may arise in the director


TODO: Exceptions should provide all info to create Error instances of the API model
For instance, assume there is a ficticious exception class FieldValidationError, then it would
translate into something like

// response - 422
{
  "error": {
    "status": 422,
    "error": "FIELDS_VALIDATION_ERROR",
    "description": "One or more fields raised validation errors."
    "fields": {
      "email": "Invalid email address.",
      "password": "Password too short."
    }
  }
}
"""
from typing import Optional

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic.errors import PydanticErrorMixin


class DirectorException(Exception):
    """Basic exception"""


class GenericDockerError(DirectorException):
    """Generic docker library error"""

    def __init__(self, msg: str, original_exception: Exception):
        super().__init__(msg + f": {original_exception}")
        self.original_exception = original_exception


class ServiceNotAvailableError(DirectorException):
    """Service not found"""

    def __init__(self, service_name: str, service_tag: Optional[str] = None):
        service_tag = service_tag or "UNDEFINED"
        super().__init__(f"The service {service_name}:{service_tag} does not exist")
        self.service_name = service_name
        self.service_tag = service_tag


class ServiceUUIDNotFoundError(DirectorException):
    """Service not found"""

    def __init__(self, service_uuid: str):
        super().__init__(f"The service with uuid {service_uuid} was not found")
        self.service_uuid = service_uuid


class ServiceUUIDInUseError(DirectorException):
    """Service UUID is already in use"""

    def __init__(self, service_uuid: str):
        super().__init__(f"The service uuid {service_uuid} is already in use")
        self.service_uuid = service_uuid


class ServiceStartTimeoutError(DirectorException):
    """The service was created but never run (time-out)"""

    def __init__(self, service_name: str, service_uuid: str):
        super().__init__(f"Service {service_name}:{service_uuid} failed to start ")
        self.service_name = service_name
        self.service_uuid = service_uuid


class ProjectNotFoundError(DirectorException):
    """Project not found error"""

    def __init__(self, project_id: ProjectID):
        super().__init__(f"project {project_id} not found")


class PipelineNotFoundError(DirectorException):
    """Pipeline not found error"""

    def __init__(self, pipeline_id: str):
        super().__init__(f"pipeline {pipeline_id} not found")


class SchedulerError(DirectorException):
    """An error in the scheduler"""

    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unexpected error in the scheduler")


class InvalidPipelineError(SchedulerError):
    """A pipeline is misconfigured"""

    def __init__(self, pipeline_id: str, msg: Optional[str] = None):
        super().__init__(msg or f"Invalid configuration of pipeline {pipeline_id}")


class TaskSchedulingError(SchedulerError):
    """A task cannot be scheduled"""

    def __init__(self, node_id: NodeID, msg: Optional[str] = None):
        super().__init__(msg=msg)
        self.node_id = node_id


class MissingComputationalResourcesError(TaskSchedulingError):
    """A task cannot be scheduled because the cluster does not have the required resources"""

    def __init__(self, node_id: NodeID, msg: Optional[str] = None):
        super().__init__(node_id, msg=msg)


class InsuficientComputationalResourcesError(TaskSchedulingError):
    """A task cannot be scheduled because the cluster does not have *enough* of the required resources"""

    def __init__(self, node_id: NodeID, msg: Optional[str] = None):
        super().__init__(node_id, msg=msg)


class ComputationalSchedulerChangedError(PydanticErrorMixin, SchedulerError):
    code = "computational_backend.scheduler_changed"
    msg_template = "The dask scheduler ID changed from '{original_scheduler_id}' to '{current_scheduler_id}'"


class ComputationalBackendNotConnectedError(PydanticErrorMixin, SchedulerError):
    code = "computational_backend.not_connected"
    msg_template = "The dask computational backend is not connected"


class ComputationalBackendTaskNotFoundError(PydanticErrorMixin, SchedulerError):
    code = "computational_backend.task_not_found"
    msg_template = (
        "The dask computational backend does not know about the task '{job_id}'"
    )


class ComputationalBackendTaskResultsNotReadyError(PydanticErrorMixin, SchedulerError):
    code = "computational_backend.task_result_not_ready"
    msg_template = "The task result is not ready yet for job '{job_id}'"


class ConfigurationError(DirectorException):
    """An error in the director-v2 configuration"""

    def __init__(self, msg: Optional[str] = None):
        super().__init__(
            msg or "Invalid configuration of the director-v2 application. Please check."
        )


class ClusterNotFoundError(PydanticErrorMixin, SchedulerError):
    code = "cluster.not_found"
    msg_template = "The cluster '{cluster_id}' not found"


class ClusterAccessForbiddenError(PydanticErrorMixin, SchedulerError):
    msg_template = "Insufficient rights to access cluster '{cluster_id}'"


class ClusterInvalidOperationError(PydanticErrorMixin, SchedulerError):
    msg_template = "Invalid operation on cluster '{cluster_id}'"


class DaskClientRequestError(PydanticErrorMixin, SchedulerError):
    code = "dask_client.request.error"
    msg_template = (
        "The dask client to cluster on '{endpoint}' did an invalid request '{error}'"
    )


class DaskClusterError(PydanticErrorMixin, SchedulerError):
    code = "cluster.error"
    msg_template = "The dask cluster on '{endpoint}' encountered an error: '{error}'"


class DaskGatewayServerError(PydanticErrorMixin, SchedulerError):
    code = "gateway.error"
    msg_template = "The dask gateway on '{endpoint}' encountered an error: '{error}'"


class DaskClientAcquisisitonError(PydanticErrorMixin, SchedulerError):
    code = "dask_client.acquisition.error"
    msg_template = (
        "The dask client to cluster '{cluster}' encountered an error '{error}'"
    )
