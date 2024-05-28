from pydantic.errors import PydanticErrorMixin


class EfsGuardianRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "efs-guardian unexpected error"


class ConfigurationError(EfsGuardianRuntimeError):
    msg_template: str = "Application misconfiguration: {msg}"
