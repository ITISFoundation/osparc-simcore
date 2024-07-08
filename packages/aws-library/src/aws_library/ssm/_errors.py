from pydantic.errors import PydanticErrorMixin


class SSMRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "SSM client unexpected error"


class SSMNotConnectedError(SSMRuntimeError):
    msg_template: str = "Cannot connect with SSM server"


class SSMAccessError(SSMRuntimeError):
    code = "SSM_access.error"
    msg_template: str = (
        "Unexpected error while accessing SSM backend: {operation_name}:{code}:{error}"
    )


class SSMSendCommandInstancesNotReadyError(SSMAccessError):
    msg_template: str = "Instance not ready to receive commands"


class SSMCommandExecutionError(SSMAccessError):
    msg_template: str = "Command execution error: {details}"


class SSMInvalidCommandIdError(SSMAccessError):
    msg_template: str = "Invalid command ID: {command_id}"
