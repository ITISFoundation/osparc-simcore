from pydantic.errors import PydanticErrorMixin


class SSMRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "SSM client unexpected error"


class SSMNotConnectedError(SSMRuntimeError):
    msg_template: str = "Cannot connect with SSM server"


class SSMAccessError(SSMRuntimeError):
    code = "SSM_access.error"
    msg_template: str = "Unexpected error while accessing SSM backend"
