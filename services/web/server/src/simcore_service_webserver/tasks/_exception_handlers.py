from common_library.user_messages import user_message
from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobMissingError,
    JobNotDoneError,
    JobSchedulerError,
    JobStatusError,
)
from models_library.api_schemas_storage.export_data_async_jobs import (
    AccessRightError,
    InvalidFileIdentifierError,
)
from servicelib.aiohttp import status

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    InvalidFileIdentifierError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Could not find file {file_id}"),
    ),
    AccessRightError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Accessright error: user {user_id} does not have access to file {file_id} with location {location_id}"
        ),
    ),
    JobAbortedError: HttpErrorInfo(
        status.HTTP_410_GONE,
        user_message("Task {job_id} is aborted"),
    ),
    JobError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message(
            "Task '{job_id}' failed with exception type '{exc_type}' and message: {exc_msg}"
        ),
    ),
    JobNotDoneError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("task {job_id} is not done yet"),
    ),
    JobMissingError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("No task with id: {job_id}"),
    ),
    JobSchedulerError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message("Encountered an error with the task scheduling system"),
    ),
    JobStatusError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message("Encountered an error while getting the status of task {job_id}"),
    ),
}


handle_export_data_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
