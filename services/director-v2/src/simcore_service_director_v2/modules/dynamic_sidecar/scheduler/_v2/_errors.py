from pydantic.errors import PydanticErrorMixin


class BaseV2SchedulerException(PydanticErrorMixin, RuntimeError):
    """base for all exceptions here"""


class BaseContextException(BaseV2SchedulerException):
    """use as base for all context related errors"""


class NotInContextError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.not_in_context"
    msg_template = "Could not find a variable named '{key}' in context: {context}"


class SetTypeMismatchError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.set_type_mismatch"
    msg_template = (
        "Found a variable named '{key}' of type='{existing_type}' and value="
        "'{existing_value}'. Trying to set to type='{new_type}' and value="
        "'{new_value}'"
    )


class GetTypeMismatchError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.get_type_mismatch"
    msg_template = (
        "Found a variable named '{key}' of type='{existing_type}' and value="
        "'{existing_value}'. Expecting type='{expected_type}'"
    )


class NotAllowedContextKeyError(BaseContextException):
    code = "dynamic_sidecar.scheduler.v2.key_not_allowed"
    msg_template = (
        "Provided key='{key}' is reserved for internal usage, "
        "please try using a different one."
    )


class BaseEventException(BaseV2SchedulerException):
    """use as base for all context related errors"""


class UnexpectedEventReturnTypeError(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.unexpected_event_return_type"
    msg_template = "Event should always return `dict[str, Any]`, returning: {type}"


class WorkflowAlreadyRunningException(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.workflow_already_running"
    msg_template = "Another workflow named '{workflow_name}' is already running"


class WorkflowNotFoundException(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.workflow_not_found"
    msg_template = "Workflow '{workflow_name}' not found"


class StateNotRegisteredException(BaseEventException):
    code = "dynamic_sidecar.scheduler.v2.state_not_registered"
    msg_template = (
        "Trying to start state '{state_name}' but these are the only"
        "available states {state_registry}"
    )
