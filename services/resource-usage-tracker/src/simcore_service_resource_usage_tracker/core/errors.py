from pydantic.errors import PydanticErrorMixin


class ResourceUsageTrackerRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "Resource-usage-tracker unexpected error"


class ConfigurationError(ResourceUsageTrackerRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"
