from common_library.errors_classes import OsparcErrorMixin


class DirectorRuntimeError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "Director-v0 unexpected error: {msg}"


class ConfigurationError(DirectorRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"


class GenericDockerError(DirectorRuntimeError):
    msg_template: str = "Docker error: {err}"


class ServiceNotAvailableError(DirectorRuntimeError):
    msg_template: str = "Service {service_name}:{service_tag} is not available"


class ServiceUUIDNotFoundError(DirectorRuntimeError):
    msg_template: str = "Service with uuid {service_uuid} was not found"


class ServiceUUIDInUseError(DirectorRuntimeError):
    msg_template: str = "Service with uuid {service_uuid} is already in use"


class ServiceStateSaveError(DirectorRuntimeError):
    msg_template: str = "Failed to save state of service {service_uuid}: {reason}"


class RegistryConnectionError(DirectorRuntimeError):
    msg_template: str = "Unexpected connection error while accessing registry: {msg}"


class ServiceStartTimeoutError(DirectorRuntimeError):
    msg_template: str = "Service {service_name}:{service_uuid} failed to start in time"
