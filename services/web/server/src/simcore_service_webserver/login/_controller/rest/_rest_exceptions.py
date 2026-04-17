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
from ....products import products_service, products_web
from ....products.errors import ProductNotFoundError
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

_logger = logging.getLogger(__name__)

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


async def _should_show_login_tip(app: web.Application, *, user_id: int, product_name: str) -> bool:
    """Show a login tip when the current product has ``marketing_login_tip_on_wrong_password``
    enabled in its vendor config AND the user also belongs to another product
    that does NOT have the flag enabled.
    """
    try:
        current_product = products_service.get_product(app, product_name=product_name)
        vendor = current_product.vendor or {}
        if not vendor.get("marketing_login_tip_on_wrong_password", False):
            return False

        for other_product in products_service.list_products(app):
            if other_product.name == product_name:
                continue
            other_vendor = other_product.vendor or {}
            if other_vendor.get("marketing_login_tip_on_wrong_password", False):
                continue
            if other_product.group_id is not None and await groups_service.is_user_in_group(
                app, user_id=user_id, group_id=other_product.group_id
            ):
                return True
    except ProductNotFoundError:
        _logger.debug(
            "Product %s not found while checking login tip for user %s",
            product_name,
            user_id,
        )
    except Exception:  # pylint: disable=broad-except
        _logger.warning(
            "Unexpected error checking login tip for user %s",
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
    product_name = products_web.get_product_name(request)
    if await _should_show_login_tip(request.app, user_id=exception.user_id, product_name=product_name):
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
