from models_library.api_schemas_rpc_async_jobs.exceptions import (
    JobAbortedError,
    JobError,
    JobNotDoneError,
    JobSchedulerError,
    JobStatusError,
)
from models_library.api_schemas_storage.data_export_async_jobs import (
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
        "Could not find file {file_id}",
    ),
    AccessRightError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Accessright error: user {user_id} does not have access to file {file_id} with location {location_id}",
    ),
    JobAbortedError: HttpErrorInfo(
        status.HTTP_410_GONE,
        "Job {job_id} is aborted",
    ),
    JobError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Job {job_id} failed with exception type {exc_type} and message {exc_msg}",
    ),
    JobNotDoneError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Job {job_id} is not done yet",
    ),
    JobSchedulerError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Encountered a an error with the job scheduling system",
    ),
    JobStatusError: HttpErrorInfo(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Encountered an error while getting the status of job {job_id}",
    ),
}


handle_data_export_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
