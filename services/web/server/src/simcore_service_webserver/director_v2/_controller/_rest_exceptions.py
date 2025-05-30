import logging

from aiohttp import web
from common_library.error_codes import create_error_code
from models_library.rest_error import ErrorGet
from servicelib import status_codes_utils
from servicelib.aiohttp import status
from servicelib.logging_errors import create_troubleshotting_log_kwargs

from ...constants import MSG_TRY_AGAIN_OR_SUPPORT
from ...exception_handling import (
    ExceptionHandlersMap,
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    create_error_context_from_request,
    create_error_response,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...users.exceptions import UserDefaultWalletNotFoundError
from ...wallets.errors import WalletNotEnoughCreditsError
from ..exceptions import DirectorV2ServiceError

_exceptions_handlers_map: ExceptionHandlersMap = {}


_logger = logging.getLogger(__name__)


async def _handler_director_service_error_as_503_or_4xx(
    request: web.Request, exception: Exception
) -> web.Response:
    assert isinstance(exception, DirectorV2ServiceError)  # nosec
    assert status_codes_utils.is_error(
        exception.status
    ), f"DirectorV2ServiceError must be an error, got {exception=}"  # nosec

    if status_codes_utils.is_5xx_server_error(exception.status):
        # NOTE: All directorv2 5XX are mapped to 503
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        user_msg = (
            # Most likely the director service is down or misconfigured so the user is asked to try again later.
            "This service is temporarily unavailable. The incident was logged and will be investigated. "
            + MSG_TRY_AGAIN_OR_SUPPORT
        )

        # Log for further investigation
        oec = create_error_code(exception)
        _logger.exception(
            **create_troubleshotting_log_kwargs(
                user_msg,
                error=exception,
                error_code=oec,
                error_context={
                    **create_error_context_from_request(request),
                    "error_code": oec,
                },
            )
        )
        error = ErrorGet.model_construct(
            message=user_msg, support_id=oec, status=status_code
        )

    else:
        # NOTE: All directorv2 4XX are mapped one-to-one
        assert status_codes_utils.is_4xx_client_error(
            exception.status
        ), f"DirectorV2ServiceError must be a client error, got {exception=}"  # nosec

        error = ErrorGet(status=exception.status, message="{exception}")

    return create_error_response(error, status_code=error.status)


_exceptions_handlers_map[DirectorV2ServiceError] = (
    _handler_director_service_error_as_503_or_4xx
)


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
