from typing import Final

from common_library.user_messages import user_message
from models_library.functions import FunctionsApiAccessRights
from models_library.functions_errors import (
    FunctionBaseError,
    FunctionJobCollectionsExecuteApiAccessDeniedError,
    FunctionJobCollectionsReadApiAccessDeniedError,
    FunctionJobCollectionsWriteApiAccessDeniedError,
    FunctionJobsExecuteApiAccessDeniedError,
    FunctionJobsReadApiAccessDeniedError,
    FunctionJobsWriteApiAccessDeniedError,
    FunctionsExecuteApiAccessDeniedError,
    FunctionsReadApiAccessDeniedError,
    FunctionsWriteApiAccessDeniedError,
)

from ..errors import WebServerBaseError


class FunctionGroupAccessRightsNotFoundError(WebServerBaseError, RuntimeError):
    msg_template = user_message(
        "Group access rights could not be found for Function '{function_id}' in product '{product_name}'."
    )


_ERRORS_MAP: Final[dict[FunctionsApiAccessRights, type[FunctionBaseError]]] = {
    FunctionsApiAccessRights.READ_FUNCTIONS: FunctionsReadApiAccessDeniedError,
    FunctionsApiAccessRights.WRITE_FUNCTIONS: FunctionsWriteApiAccessDeniedError,
    FunctionsApiAccessRights.EXECUTE_FUNCTIONS: FunctionsExecuteApiAccessDeniedError,
    FunctionsApiAccessRights.READ_FUNCTION_JOBS: FunctionJobsReadApiAccessDeniedError,
    FunctionsApiAccessRights.WRITE_FUNCTION_JOBS: FunctionJobsWriteApiAccessDeniedError,
    FunctionsApiAccessRights.EXECUTE_FUNCTION_JOBS: FunctionJobsExecuteApiAccessDeniedError,
    FunctionsApiAccessRights.READ_FUNCTION_JOB_COLLECTIONS: FunctionJobCollectionsReadApiAccessDeniedError,
    FunctionsApiAccessRights.WRITE_FUNCTION_JOB_COLLECTIONS: FunctionJobCollectionsWriteApiAccessDeniedError,
    FunctionsApiAccessRights.EXECUTE_FUNCTION_JOB_COLLECTIONS: FunctionJobCollectionsExecuteApiAccessDeniedError,
}
