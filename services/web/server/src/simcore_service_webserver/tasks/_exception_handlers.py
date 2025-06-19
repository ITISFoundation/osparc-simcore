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
        user_message(
            "The file with identifier {file_id} could not be found", _version=2
        ),
    ),
    AccessRightError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Permission denied: You (user {user_id}) don't have the necessary rights to access file {file_id} in location {location_id}",
            _version=2,
        ),
    ),
    JobAbortedError: HttpErrorInfo(
        status.HTTP_410_GONE,
        user_message("Task {job_id} was terminated before completion", _version=2),
    ),
    JobError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message(
            "Task '{job_id}' encountered an error: {exc_msg} (error type: '{exc_type}')",
            _version=2,
        ),
    ),
    JobNotDoneError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "Task {job_id} is still running and has not completed yet", _version=2
        ),
    ),
    JobMissingError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested task with ID {job_id} does not exist", _version=2),
    ),
    JobSchedulerError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message(
            "The task scheduling system encountered an error. Please try again later",
            _version=2,
        ),
    ),
    JobStatusError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        user_message("Unable to get the current status for task {job_id}", _version=2),
    ),
}


handle_export_data_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
