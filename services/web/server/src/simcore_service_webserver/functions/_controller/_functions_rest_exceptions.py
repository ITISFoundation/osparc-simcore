from models_library.functions_errors import (
    FunctionIDNotFoundError,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobIDNotFoundError,
    UnsupportedFunctionClassError,
    UnsupportedFunctionFunctionJobClassCombinationError,
    UnsupportedFunctionJobClassError,
)
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    FunctionIDNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Function id {function_id} was not found",
    ),
    UnsupportedFunctionClassError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Function class {function_class} is not supported. ",
    ),
    UnsupportedFunctionJobClassError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Function job class {function_job_class} is not supported. ",
    ),
    UnsupportedFunctionFunctionJobClassCombinationError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Function class {function_class} and function job class {function_job_class} "
        "combination is not supported. ",
    ),
    FunctionJobIDNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Function job id {function_job_id} was not found",
    ),
    FunctionJobCollectionIDNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Function job collection id {function_job_collection_id} was not found",
    ),
}


handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
