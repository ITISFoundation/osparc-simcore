import logging
from pprint import pformat
from typing import Any

from models_library.error_codes import ErrorCodeStr, create_error_code
from models_library.errors_classes import OsparcErrorMixin

from .logging_errors import get_log_record_extra

_logger = logging.getLogger(__name__)


def create_troubleshotting_log_message(
    message_to_user: str,
    error: BaseException,
    error_code: ErrorCodeStr,
    error_context: dict[str, Any] | None = None,
    tip: str | None = None,
) -> str:
    """Create a formatted message for _logger.exception(...)

    Arguments:
        message_to_user -- A user-friendly message to be displayed on the front-end explaining the issue in simple terms.
        error -- the instance of the handled exception
        error_code -- A unique error code (e.g., OEC or osparc-specific) to identify the type or source of the error for easier tracking.
        error_context -- Additional context surrounding the exception, such as environment variables or function-specific data. This can be derived from exc.error_context() (relevant when using the OsparcErrorMixin)
        tip -- Helpful suggestions or possible solutions explaining why the error may have occurred and how it could potentially be resolved
    """
    debug_data = pformat(
        {
            "exception_details": f"{error}",
            "error_code": error_code,
            "context": pformat(error_context, indent=1),
            "tip": tip,
        },
        indent=1,
    )

    return f"{message_to_user}.\n{debug_data}"


def create_troubleshotting_log_kwargs(
    message_to_user: str,
    exception: BaseException,
    error_context: dict[str, Any] | None = None,
    tip: str | None = None,
):
    error_code = create_error_code(exception)

    context = error_context or {}
    if isinstance(exception, OsparcErrorMixin):
        context.update(exception.error_context())

    log_msg = create_troubleshotting_log_message(
        message_to_user=message_to_user,
        error=exception,
        error_code=error_code,
        error_context=context,
        tip=tip,
    )

    return {
        "msg": log_msg,
        "extra": get_log_record_extra(
            error_code=error_code,
            user_id=context.get("user_id", None),
        ),
    }
