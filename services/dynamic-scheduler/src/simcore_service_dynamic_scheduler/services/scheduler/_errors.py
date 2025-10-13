from common_library.errors_classes import OsparcErrorMixin


class BaseSchedulerError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class UnexpectedCouldNotFindCurrentScheduledIdError(BaseSchedulerError):
    msg_template: str = "Could not find current_schedule_id, this is unexpected"


class UnexpectedCouldNotFindOperationNameError(BaseSchedulerError):
    msg_template: str = "Could not find operation name for schedule_id '{schedule_id}'"


class UnexpectedCouldNotDetermineOperationTypeError(BaseSchedulerError):
    msg_template: str = (
        "Could not determine operation type from '{operation_name}'. Supported types are {supported_types}"
    )
