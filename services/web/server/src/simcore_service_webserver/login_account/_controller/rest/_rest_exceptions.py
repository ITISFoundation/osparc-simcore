from ....exception_handling import (
    ExceptionToHttpErrorMap,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ....login._controller.rest._rest_exceptions import (
    _TO_HTTP_ERROR_MAP as LOGIN_TO_HTTP_ERROR_MAP,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {**LOGIN_TO_HTTP_ERROR_MAP}


handle_rest_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
