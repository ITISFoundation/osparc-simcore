from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..errors import MissingStripeConfigError, ProductNotFoundError

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    ProductNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND, "{product_name} was not found"
    ),
    MissingStripeConfigError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE, MissingStripeConfigError.msg_template
    ),
}


handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
