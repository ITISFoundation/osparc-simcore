from common_library.user_messages import user_message
from fastapi import status

from .backend_errors import BaseBackEndError


class TaskSchedulerError(BaseBackEndError):
    msg_template: str = user_message(
        "An error occurred in the task scheduler.", _version=1
    )
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class TaskMissingError(BaseBackEndError):
    msg_template: str = user_message("Task {job_id} could not be found.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class TaskResultMissingError(BaseBackEndError):
    msg_template: str = user_message("Task {job_id} has not completed yet.", _version=1)
    status_code = status.HTTP_404_NOT_FOUND


class TaskCancelledError(BaseBackEndError):
    msg_template: str = user_message("Task {job_id} has been cancelled.", _version=1)
    status_code = status.HTTP_409_CONFLICT


class TaskError(BaseBackEndError):
    msg_template: str = user_message(
        "Task '{job_id}' encountered an error.", _version=1
    )
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
