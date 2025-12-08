from common_library.errors_classes import OsparcErrorMixin


class BaseGenericSchedulerError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class NoDataFoundError(BaseGenericSchedulerError):
    msg_template: str = "Key '{key}' not found in hash '{hash_key}'"


class OperationAlreadyRegisteredError(BaseGenericSchedulerError):
    msg_template: str = "Operation '{operation_name}' already registered"


class OperationNotFoundError(BaseGenericSchedulerError):
    msg_template: str = (
        "Operation '{operation_name}' was not found, registered_operations='{registered_operations}'"
    )


class OperationInitialContextKeyNotFoundError(BaseGenericSchedulerError):
    msg_template: str = (
        "Operation '{operation_name}' required_key='{required_key}' not in initial_operation_context"
    )


class StepNotFoundInOperationError(BaseGenericSchedulerError):
    msg_template: str = (
        "Step '{step_name}' not found steps_names='{steps_names}' for operation '{operation_name}'"
    )


class UnexpectedStepHandlingError(BaseGenericSchedulerError):
    msg_template: str = (
        "During '{direction}' of steps_statuses='{steps_statuses}' for schedule_id='{schedule_id}' "
        "reached the end of the handler. This should not happen."
    )


class OperationContextValueIsNoneError(BaseGenericSchedulerError):
    msg_template: str = "Values of context cannot be None: {operation_context}"


class ProvidedOperationContextKeysAreMissingError(BaseGenericSchedulerError):
    msg_template: str = (
        "Provided context {provided_context} is missing keys {missing_keys}, was expecting {expected_keys}"
    )


class InitialOperationContextKeyNotAllowedError(BaseGenericSchedulerError):
    msg_template: str = (
        "Initial operation context cannot contain key '{key}' that would "
        "be overritted by a step in the operation: {operation}"
    )


class OperationNotCancellableError(BaseGenericSchedulerError):
    msg_template: str = "Operation '{operation_name}' is not cancellable"


class CannotCancelWhileWaitingForManualInterventionError(BaseGenericSchedulerError):
    msg_template: str = (
        "Cannot cancel schedule_id='{schedule_id}' while one or more steps are waiting for manual intervention."
    )


class StepNameNotInCurrentGroupError(BaseGenericSchedulerError):
    msg_template: str = (
        "step_name='{step_name}' not in current step_group_name='{step_group_name}' of operation_name='{operation_name}'"
    )


class StepNotInErrorStateError(BaseGenericSchedulerError):
    msg_template: str = (
        "step_name='{step_name}' is not in an error state and cannot be restarted"
    )


class StepNotWaitingForManualInterventionError(BaseGenericSchedulerError):
    msg_template: str = "step_name='{step_name}' is not waiting for manual intervention"
