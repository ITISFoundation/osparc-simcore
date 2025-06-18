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
        user_message("File {file_id} could not be found", _version=1),
    ),
    AccessRightError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Access denied: User {user_id} does not have permission to access file {file_id} in location {location_id}",
            _version=1,
        ),
    ),
    JobAbortedError: HttpErrorInfo(
        status.HTTP_410_GONE,
        user_message("Task {job_id} has been aborted", _version=1),
    ),
    JobError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message(
            "Task '{job_id}' failed with error type '{exc_type}': {exc_msg}", _version=1
        ),
    ),
    JobNotDoneError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Task {job_id} is still in progress", _version=1),
    ),
    JobMissingError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Task with ID {job_id} was not found", _version=1),
    ),
    JobSchedulerError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message("An error occurred in the task scheduling system", _version=1),
    ),
    JobStatusError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message("Failed to retrieve status for task {job_id}", _version=1),
    ),
}


handle_export_data_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
