from pydantic.errors import PydanticErrorMixin


class AgentRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Autoscaling unexpected error"


class ConfigurationError(AgentRuntimeError):
    code: str = "agent.application_configuration"
    msg_template: str = "Application misconfiguration: {msg}"


class CouldNotRemoveVolumesError(AgentRuntimeError):
    code: str = "agent.volume_removal.failed_to_remove"
    msg_template: str = "There were errors while removing one or more volumes: {errors}"
