from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...constants import MSG_TRY_AGAIN_OR_SUPPORT
from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..errors import MissingStripeConfigError, ProductNotFoundError

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    ProductNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("{product_name} was not found"),
    ),
    MissingStripeConfigError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "{product_name} service is currently unavailable."
            + MSG_TRY_AGAIN_OR_SUPPORT
        ),
    ),
}


handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
