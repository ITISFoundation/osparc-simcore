from common_library.errors_classes import OsparcErrorMixin
from servicelib.aiohttp import status  # type: ignore


class FunctionBaseError(OsparcErrorMixin, Exception):
    status_code: int


class FunctionJobReadAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} read access denied for user {user_id}"
    )
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function {function_id} not found"
    status_code: int = status.HTTP_404_NOT_FOUND


class FunctionJobIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job {function_job_id} not found"
    status_code: int = status.HTTP_404_NOT_FOUND


class FunctionInputsValidationError(FunctionBaseError):
    msg_template: str = "Function inputs validation failed: {error}"
    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY


class FunctionReadAccessDeniedError(FunctionBaseError):
    msg_template: str = "Function {function_id} read access denied for user {user_id}"
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionJobCollectionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job collection {function_job_collection_id} not found"
    status_code: int = status.HTTP_404_NOT_FOUND


class UnsupportedFunctionClassError(FunctionBaseError):
    msg_template: str = "Function class {function_class} is not supported"
    status_code: int = status.HTTP_400_BAD_REQUEST


class UnsupportedFunctionJobClassError(FunctionBaseError):
    msg_template: str = "Function job class {function_job_class} is not supported"
    status_code: int = status.HTTP_400_BAD_REQUEST


class UnsupportedFunctionFunctionJobClassCombinationError(FunctionBaseError):
    msg_template: str = (
        "Function class {function_class} and function job class {function_job_class} combination is not supported"
    )
    status_code: int = status.HTTP_400_BAD_REQUEST


class FunctionJobCollectionReadAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} read access denied for user {user_id}"
    )
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = "Function {function_id} write access denied for user {user_id}"
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionJobWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} write access denied for user {user_id}"
    )
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionJobCollectionWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} write access denied for user {user_id}"
    )
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function {function_id} execute access denied for user {user_id}"
    )
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionJobExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} execute access denied for user {user_id}"
    )
    status_code: int = status.HTTP_403_FORBIDDEN


class FunctionJobCollectionExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} execute access denied for user {user_id}"
    )
    status_code: int = status.HTTP_403_FORBIDDEN
