from fastapi import status

from .backend_errors import BaseBackEndError


class TaskBaseError(BaseBackEndError):
    pass


class TaskSchedulerError(TaskBaseError):
    msg_template: str = "TaskScheduler error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class TaskMissingError(TaskBaseError):
    msg_template: str = "Task {job_id} does not exist"
    status_code = status.HTTP_404_NOT_FOUND


class TaskStatusError(TaskBaseError):
    msg_template: str = "Could not get status of task {job_id}"
    status_code = status.HTTP_404_NOT_FOUND


class TaskNotDoneError(TaskBaseError):
    msg_template: str = "Task {job_id} not done"
    status_code = status.HTTP_409_CONFLICT


class TaskCancelledError(TaskBaseError):
    msg_template: str = "Task {job_id} cancelled"
    status_code = status.HTTP_409_CONFLICT


class TaskError(TaskBaseError):
    msg_template: str = "Task '{job_id}' failed"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
