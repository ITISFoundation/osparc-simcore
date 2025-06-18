import inspect
import sys

from common_library.user_messages import user_message

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)

# Get all classes defined in functions_errors
function_error_classes = [
    obj
    for name, obj in inspect.getmembers(sys.modules["models_library.functions_errors"])
    if inspect.isclass(obj)
    and obj.__module__.startswith("models_library.functions_errors")
]

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    # Dynamically create error mappings for all function-related errors
    cls: HttpErrorInfo(
        status_code=cls.status_code,
        msg_template=user_message(cls.msg_template),
    )
    for cls in function_error_classes
    if hasattr(cls, "status_code") and hasattr(cls, "msg_template")
}

handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
