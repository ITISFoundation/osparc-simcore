from common_library.errors_classes import OsparcErrorMixin


class FunctionBaseError(OsparcErrorMixin, Exception):
    pass


class FunctionJobReadAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} read access denied for user {user_id}"
    )


class FunctionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function {function_id} not found"


class FunctionJobIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job {function_job_id} not found"


class FunctionInputsValidationError(FunctionBaseError):
    msg_template: str = "Function inputs validation failed: {error}"


class FunctionReadAccessDeniedError(FunctionBaseError):
    msg_template: str = "Function {function_id} read access denied for user {user_id}"


class FunctionJobCollectionIDNotFoundError(FunctionBaseError):
    msg_template: str = "Function job collection {function_job_collection_id} not found"


class UnsupportedFunctionClassError(FunctionBaseError):
    msg_template: str = "Function class {function_class} is not supported"


class UnsupportedFunctionJobClassError(FunctionBaseError):
    msg_template: str = "Function job class {function_job_class} is not supported"


class UnsupportedFunctionFunctionJobClassCombinationError(FunctionBaseError):
    msg_template: str = (
        "Function class {function_class} and function job class {function_job_class} combination is not supported"
    )


class FunctionJobCollectionReadAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} read access denied for user {user_id}"
    )


class FunctionWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = "Function {function_id} write access denied for user {user_id}"


class FunctionJobWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} write access denied for user {user_id}"
    )


class FunctionJobCollectionWriteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} write access denied for user {user_id}"
    )


class FunctionExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function {function_id} execute access denied for user {user_id}"
    )


class FunctionJobExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job {function_job_id} execute access denied for user {user_id}"
    )


class FunctionJobCollectionExecuteAccessDeniedError(FunctionBaseError):
    msg_template: str = (
        "Function job collection {function_job_collection_id} execute access denied for user {user_id}"
    )
