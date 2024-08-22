from pydantic.errors import PydanticErrorMixin


class SSMRuntimeError(PydanticErrorMixin, RuntimeError):
    msg_template: str = "SSM client unexpected error"


class SSMNotConnectedError(SSMRuntimeError):
    msg_template: str = "Cannot connect with SSM server"


class SSMAccessError(SSMRuntimeError):
    msg_template: str = (
        "Unexpected error while accessing SSM backend: {operation_name}:{code}:{error}"
    )


class SSMTimeoutError(SSMAccessError):
    msg_template: str = "Timeout while accessing SSM backend: {details}"


class SSMSendCommandInstancesNotReadyError(SSMAccessError):
    msg_template: str = "Instance not ready to receive commands"


class SSMCommandExecutionResultError(SSMAccessError):
    msg_template: str = "Command {id}:{name} execution resulted in an error: {details}"


class SSMCommandExecutionTimeoutError(SSMAccessError):
    msg_template: str = "Command execution timed-out: {details}"


class SSMInvalidCommandError(SSMAccessError):
    msg_template: str = "Invalid command ID: {command_id}"
