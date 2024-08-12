from pydantic.errors import PydanticErrorMixin


class ClustersKeeperRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "clusters-keeper unexpected error"


class ConfigurationError(ClustersKeeperRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"
