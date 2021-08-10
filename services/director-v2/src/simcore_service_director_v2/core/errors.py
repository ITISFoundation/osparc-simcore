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


class DirectorException(Exception):
    """Basic exception"""

    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unexpected error was triggered")


class GenericDockerError(DirectorException):
    """Generic docker library error"""

    def __init__(self, msg: str, original_exception: Exception):
        super().__init__(msg + f": {original_exception.message}")
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


class ConfigurationError(DirectorException):
    """An error in the director-v2 configuration"""

    def __init__(self, msg: Optional[str]):
        super().__init__(
            msg or "Invalid configuration of the director-v2 application. Please check."
        )
