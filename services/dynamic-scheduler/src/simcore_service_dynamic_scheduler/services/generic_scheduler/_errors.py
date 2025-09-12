from common_library.errors_classes import OsparcErrorMixin


class BaseGenericSchedulerError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class KeyNotFoundInHashError(BaseGenericSchedulerError):
    msg_template: str = "Key '{key}' not found in hash '{hash_key}'"


class OperationAlreadyRegisteredError(BaseGenericSchedulerError):
    msg_template: str = "Operation '{operation_name}' already registered"


class OperationNotFoundError(BaseGenericSchedulerError):
    msg_template: str = (
        "Operation '{operation_name}' was not found, registerd_operations='{registerd_operations}'"
    )


class StepNotFoundInoperationError(BaseGenericSchedulerError):
    msg_template: str = (
        "Step '{step_name}' not found registerd_steps='{steps_names}' for operation '{operation_name}'"
    )


class GroupNotFoundInOperationError(BaseGenericSchedulerError):
    msg_template: str = (
        "Group with index '{group_index}' not found for operation '{operation_name}' "
        "which has '{operations_count}' groups"
    )


class UnexpectedStepHandlingError(BaseGenericSchedulerError):
    msg_template: str = (
        "During '{direction}' of steps_statuses='{steps_statuses}' for schedule_id='{schedule_id}' "
        "reached the end of the handler. This should not happen."
    )
