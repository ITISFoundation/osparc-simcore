from pydantic.errors import PydanticErrorMixin


class AgentRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Autoscaling unexpected error"


class ConfigurationError(AgentRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"
