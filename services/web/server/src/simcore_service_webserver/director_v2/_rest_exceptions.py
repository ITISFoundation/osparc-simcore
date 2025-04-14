from aiohttp import web
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_responses import create_http_error
from servicelib.aiohttp.web_exceptions_extension import get_http_error_class_or_none
from simcore_service_webserver.director_v2.exceptions import DirectorServiceError

from ..exception_handling import (
    ExceptionHandlersMap,
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..users.exceptions import UserDefaultWalletNotFoundError
from ..wallets.errors import WalletNotEnoughCreditsError

_exceptions_handlers_map: ExceptionHandlersMap = {}


async def _handler_director_service_error(
    request: web.Request, exception: Exception
) -> web.Response:
    assert request  # nosec

    assert isinstance(exception, DirectorServiceError)  # nosec
    return create_http_error(
        exception,
        reason=exception.reason,
        http_error_cls=get_http_error_class_or_none(exception.status)
        or web.HTTPServiceUnavailable,
    )


_exceptions_handlers_map[DirectorServiceError] = _handler_director_service_error


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    UserDefaultWalletNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Default wallet not found but necessary for computations",
    ),
    WalletNotEnoughCreditsError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Wallet does not have enough credits for computations. {reason}",
    ),
}

_exceptions_handlers_map.update(to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP))

handle_rest_requests_exceptions = exception_handling_decorator(_exceptions_handlers_map)
