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
