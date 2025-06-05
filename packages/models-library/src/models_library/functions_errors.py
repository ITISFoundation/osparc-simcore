from common_library.errors_classes import OsparcErrorMixin


class FunctionBaseError(OsparcErrorMixin, Exception):
    status_code: int


class FunctionJobReadAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} read access denied for user {user_id}"
    )
    status_code: int = 403  # Forbidden


class FunctionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function {function_id} not found"
    status_code: int = 404  # Not Found


class FunctionJobIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job {function_job_id} not found"
    status_code: int = 404  # Not Found


class FunctionInputsValidationError(FunctionBaseError):
    msg_template: str = "Function inputs validation failed: {error}"
    status_code: int = 422  # Unprocessable Entity


class FunctionReadAccessDeniedError(FunctionBaseError):
    msg_template: str = "Function {function_id} read access denied for user {user_id}"
    status_code: int = 403  # Forbidden


class FunctionJobCollectionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job collection {function_job_collection_id} not found"
    status_code: int = 404  # Not Found


class UnsupportedFunctionClassError(FunctionBaseError):
    msg_template: str = "Function class {function_class} is not supported"
    status_code: int = 400  # Bad Request


class UnsupportedFunctionJobClassError(FunctionBaseError):
    msg_template: str = "Function job class {function_job_class} is not supported"
    status_code: int = 400  # Bad Request


class UnsupportedFunctionFunctionJobClassCombinationError(FunctionBaseError):
    msg_template: str = (
        "Function class {function_class} and function job class {function_job_class} combination is not supported"
    )
    status_code: int = 400  # Bad Request


class FunctionJobCollectionReadAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} read access denied for user {user_id}"
    )
    status_code: int = 403  # Forbidden


class FunctionWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = "Function {function_id} write access denied for user {user_id}"
    status_code: int = 403  # Forbidden


class FunctionJobWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} write access denied for user {user_id}"
    )
    status_code: int = 403  # Forbidden


class FunctionJobCollectionWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} write access denied for user {user_id}"
    )
    status_code: int = 403  # Forbidden


class FunctionExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function {function_id} execute access denied for user {user_id}"
    )
    status_code: int = 403  # Forbidden


class FunctionJobExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} execute access denied for user {user_id}"
    )
    status_code: int = 403  # Forbidden


class FunctionJobCollectionExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} execute access denied for user {user_id}"
    )
    status_code: int = 403  # Forbidden
