import logging
from typing import Any, TypedDict

from common_library.error_codes import ErrorCodeStr
from common_library.errors_classes import OsparcErrorMixin
from common_library.json_serialization import json_dumps, representation_encoder

from .logging_utils import LogExtra, get_log_record_extra

_logger = logging.getLogger(__name__)


def create_troubleshotting_log_message(
    user_error_msg: str,
    *,
    error: BaseException,
    error_code: ErrorCodeStr | None = None,
    error_context: dict[str, Any] | None = None,
    tip: str | None = None,
) -> str:
    """Create a formatted message for _logger.exception(...)

    Arguments:
        user_error_msg -- A user-friendly message to be displayed on the front-end explaining the issue in simple terms.
        error -- the instance of the handled exception
        error_code -- A unique error code (e.g., OEC or osparc-specific) to identify the type or source of the error for easier tracking.
        error_context -- Additional context surrounding the exception, such as environment variables or function-specific data. This can be derived from exc.error_context() (relevant when using the OsparcErrorMixin)
        tip -- Helpful suggestions or possible solutions explaining why the error may have occurred and how it could potentially be resolved
    """

    def _collect_causes(exc: BaseException) -> str:
        causes = []
        current = exc.__cause__
        while current is not None:
            causes.append(f"[{type(current).__name__}]'{current}'")
            current = getattr(current, "__cause__", None)
        return " <- ".join(causes)

    debug_data = json_dumps(
        {
            "exception_type": f"{type(error)}",
            "exception_string": f"{error}",
            "exception_causes": _collect_causes(error),
            "error_code": error_code,
            "context": error_context,
            "tip": tip,
        },
        default=representation_encoder,
        indent=1,
    )

    return f"{user_error_msg}.\n{debug_data}"


class LogKwargs(TypedDict):
    msg: str
    extra: LogExtra | None


def create_troubleshotting_log_kwargs(
    user_error_msg: str,
    *,
    error: BaseException,
    error_code: ErrorCodeStr | None = None,
    error_context: dict[str, Any] | None = None,
    tip: str | None = None,
) -> LogKwargs:
    """
    Creates a dictionary of logging arguments to be used with _log.exception for troubleshooting purposes.

    Usage:

        try:
            ...
        except MyException as exc
            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    user_error_msg=frontend_msg,
                    exception=exc,
                    tip="Check row in `groups_extra_properties` for this product. It might be missing.",
                )
            )

    """
    # error-context
    context = error_context or {}
    if isinstance(error, OsparcErrorMixin):
        context.update(error.error_context())

    # compose as log message
    log_msg = create_troubleshotting_log_message(
        user_error_msg,
        error=error,
        error_code=error_code,
        error_context=context,
        tip=tip or getattr(error, "tip", None),
    )

    return {
        "msg": log_msg,
        "extra": get_log_record_extra(
            error_code=error_code,
            user_id=context.get("user_id", None),
        ),
    }
