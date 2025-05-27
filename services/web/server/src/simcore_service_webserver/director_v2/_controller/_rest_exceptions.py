from servicelib.aiohttp import status
from simcore_service_webserver.constants import MSG_TRY_AGAIN_OR_SUPPORT
from simcore_service_webserver.director_v2.exceptions import DirectorServiceError

from ...exception_handling import (
    ExceptionHandlersMap,
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...users.exceptions import UserDefaultWalletNotFoundError
from ...wallets.errors import WalletNotEnoughCreditsError

_exceptions_handlers_map: ExceptionHandlersMap = {}


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    UserDefaultWalletNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Default wallet not found but necessary for computations",
    ),
    WalletNotEnoughCreditsError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Wallet does not have enough credits for computations. {reason}",
    ),
    DirectorServiceError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "This service is temporarily unavailable. The incident was logged and will be investigated. "
        + MSG_TRY_AGAIN_OR_SUPPORT,
    ),
}

_exceptions_handlers_map.update(to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP))

handle_rest_requests_exceptions = exception_handling_decorator(_exceptions_handlers_map)
