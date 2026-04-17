import logging

from aiohttp import web
from common_library.user_messages import user_message
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_middlewares import handle_aiohttp_web_http_error

from ....exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ....groups import api as groups_service
from ....products import products_service
from ....users.exceptions import AlreadyPreRegisteredError
from ...constants import (
    MSG_2FA_UNAVAILABLE,
    MSG_WRONG_PASSWORD,
    MSG_WRONG_PASSWORD_MERGED_ACCOUNTS,
)
from ...errors import (
    SendingVerificationEmailError,
    SendingVerificationSmsError,
    WrongPasswordError,
)

log = logging.getLogger(__name__)

# Products involved in the sim4life.io / sim4life.science database merge.
# Users that belong to multiple of these products get a targeted
# wrong-password message informing them about unified login.
_MERGED_PRODUCT_NAMES: set[str] = {"s4l", "s4llite"}

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    AlreadyPreRegisteredError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "An account for the email {email} has been submitted. "
            "If you haven't received any updates, please contact support.",
            _version=1,
        ),
    ),
    SendingVerificationSmsError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        MSG_2FA_UNAVAILABLE,
    ),
    SendingVerificationEmailError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        MSG_2FA_UNAVAILABLE,
    ),
}


async def _is_user_affected_by_db_merge(app: web.Application, *, user_id: int) -> bool:
    """Checks if user belongs to all products involved in the DB merge."""
    try:
        for product_name in _MERGED_PRODUCT_NAMES:
            product = products_service.get_product(app, product_name=product_name)
            if product.group_id is None or not await groups_service.is_user_in_group(
                app, user_id=user_id, group_id=product.group_id
            ):
                return False
        return True
    except Exception:  # pylint: disable=broad-except
        log.warning(
            "Failed to check merged-accounts status for user %s",
            user_id,
            exc_info=True,
        )
    return False


async def _handle_legacy_error_response(request: web.Request, exception: Exception):
    """
    This handlers keeps compatibility with error responses that include deprecated
    `ErrorGet.errors` field

    SEE packages/models-library/src/models_library/rest_error.py
    """
    assert isinstance(  # nosec
        exception, WrongPasswordError
    ), f"Expected WrongPasswordError, got {type(exception)}"

    msg = MSG_WRONG_PASSWORD
    user_id: int | None = getattr(exception, "user_id", None)
    if user_id is not None and await _is_user_affected_by_db_merge(request.app, user_id=user_id):
        msg = MSG_WRONG_PASSWORD_MERGED_ACCOUNTS

    return handle_aiohttp_web_http_error(
        request=request,
        exception=web.HTTPUnauthorized(text=msg),
    )


handle_rest_requests_exceptions = exception_handling_decorator(
    {
        **to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP),
        WrongPasswordError: _handle_legacy_error_response,
    },
)
