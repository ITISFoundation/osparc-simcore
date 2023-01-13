from pydantic.errors import PydanticErrorMixin


class BaseSchedulerException(PydanticErrorMixin, RuntimeError):
    """base for all exceptions here"""


class BaseContextException(BaseSchedulerException):
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


class UnexpectedStepReturnTypeError(BaseSchedulerException):
    code = "dynamic_sidecar.scheduler.v2.unexpected_step_return_type"
    msg_template = "Step should always return `dict[str, Any]`, returning: {type}"


class BaseWorkflowException(BaseSchedulerException):
    """use as base for all workflow related errors"""


class WorkflowAlreadyRunningException(BaseWorkflowException):
    code = "dynamic_sidecar.scheduler.v2.workflow_already_running"
    msg_template = "Another workflow named '{workflow_name}' is already running"


class WorkflowNotFoundException(BaseWorkflowException):
    code = "dynamic_sidecar.scheduler.v2.workflow_not_found"
    msg_template = "Workflow '{workflow_name}' not found"


class WorkflowNotInitializedException(BaseWorkflowException):
    code = "dynamic_sidecar.scheduler.v2.workflow_not_initialized_found"
    msg_template = "Workflow '{workflow_name}' has to be initialized before using this."


class InvalidSerializedContextException(BaseWorkflowException):
    code = "dynamic_sidecar.scheduler.v2.invalid_serialized_context_for_workflow"
    msg_template = (
        "Trying to resume workflow '{workflow_name}' from an invalid "
        "context '{serialized_context}'"
    )


class BaseActionException(BaseSchedulerException):
    """use as base for all action related errors"""


class ActionNotRegisteredException(BaseActionException):
    code = "dynamic_sidecar.scheduler.v2.action_not_registered"
    msg_template = (
        "Trying to start action '{action_name}' but these are the only"
        "available actions {workflow}"
    )


class OnErrorActionNotInWorkflowException(BaseActionException):
    code = "dynamic_sidecar.scheduler.v2.on_error_action_not_in_workflow"
    msg_template = (
        "Action '{action_name}' defines an on_error_action '{on_error_action}'"
        "that is not in the present in the workflow {workflow}"
    )


class NextActionNotInWorkflowException(BaseActionException):
    code = "dynamic_sidecar.scheduler.v2.next_action_not_in_workflow"
    msg_template = (
        "Action '{action_name}' defines an next_action '{next_action}'"
        "that is not in the present in the workflow {workflow}"
    )
