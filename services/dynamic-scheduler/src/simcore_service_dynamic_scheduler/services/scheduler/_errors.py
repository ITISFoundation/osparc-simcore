from common_library.errors_classes import OsparcErrorMixin


class BaseSchedulerError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class UnexpectedCouldNotDetermineOperationTypeError(BaseSchedulerError):
    msg_template: str = (
        "Could not determine operation type from '{operation_name}'. Supported types are {supported_types}"
    )
