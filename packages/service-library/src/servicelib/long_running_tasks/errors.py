from common_library.errors_classes import OsparcErrorMixin


class BaseLongRunningError(OsparcErrorMixin, Exception):
    """base exception for this module"""


class TaskNotRegisteredError(BaseLongRunningError):
    msg_template: str = (
        "no task with task_name='{task_name}' was found in the task registry. "
        "Make sure it's registered before starting it."
    )


class TaskAlreadyRunningError(BaseLongRunningError):
    msg_template: str = "{task_name} must be unique, found: '{managed_task}'"


class TaskNotFoundError(BaseLongRunningError):
    msg_template: str = "No task with {task_id} found"


class TaskNotCompletedError(BaseLongRunningError):
    msg_template: str = "Task {task_id} has not finished yet"


class TaskCancelledError(BaseLongRunningError):
    msg_template: str = "Task {task_id} was cancelled before completing"


class TaskExceptionError(BaseLongRunningError):
    msg_template: str = (
        "Task {task_id} finished with exception: '{exception}'\n{traceback}"
    )


class TaskClientTimeoutError(BaseLongRunningError):
    msg_template: str = (
        "Timed out after {timeout} seconds while awaiting '{task_id}' to complete"
    )


class GenericClientError(BaseLongRunningError):
    msg_template: str = (
        "Unexpected error while '{action}' for '{task_id}': status={status} body={body}"
    )
