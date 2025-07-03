from fastapi import status

from .backend_errors import BaseBackEndError


class TaskSchedulerError(BaseBackEndError):
    msg_template: str = "TaskScheduler error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class TaskMissingError(BaseBackEndError):
    msg_template: str = "Task {job_id} does not exist"
    status_code = status.HTTP_404_NOT_FOUND


class TaskResultMissingError(BaseBackEndError):
    msg_template: str = "Task {job_id} is not done"
    status_code = status.HTTP_404_NOT_FOUND


class TaskCancelledError(BaseBackEndError):
    msg_template: str = "Task {job_id} is cancelled"
    status_code = status.HTTP_409_CONFLICT


class TaskError(BaseBackEndError):
    msg_template: str = "Task '{job_id}' failed"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
