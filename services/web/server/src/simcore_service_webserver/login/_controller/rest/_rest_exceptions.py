import logging

from aiohttp import web
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
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


async def _try_show_login_fallbacks_on_wrong_password(
    app: web.Application, *, user_id: int, product_name: str
) -> str | None:
    """Returns the suggested product display name when a login tip should be shown.

    Checks if the current product has ``marketing_fallback_products_on_wrong_password``
    configured with a list of product names. If the user belongs to any of those
    products, returns the display name of the matching product.
    """
    try:
        current_product = products_service.get_product(app, product_name=product_name)
        vendor = current_product.vendor or {}
        tip_products: list[str] = vendor.get("marketing_fallback_products_on_wrong_password", [])
        if not tip_products:
            return None

        for check_product_name in tip_products:
            try:
                check_product = products_service.get_product(app, product_name=check_product_name)
            except ProductNotFoundError:
                continue
            if check_product.group_id is not None and await groups_service.is_user_in_group(
                app, user_id=user_id, group_id=check_product.group_id
            ):
                return check_product.display_name
    except Exception as exc:  # pylint: disable=broad-except
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                "Unexpected error checking login",
                error=exc,
                error_context={
                    "user_id": user_id,
                    "product_name": product_name,
                },
            )
        )
    return None


async def _handle_legacy_error_response(request: web.Request, exception: Exception):
    """
    This handlers keeps compatibility with error responses that include deprecated
    `ErrorGet.errors` field

    SEE packages/models-library/src/models_library/rest_error.py
    """
    assert isinstance(  # nosec
        exception, WrongPasswordError
    ), f"Expected WrongPasswordError, got {type(exception)}"

    user_id = exception.error_context().get("user_id")
    assert user_id is not None, "user_id must be present in error context"  # nosec

    msg = MSG_WRONG_PASSWORD
    product_name = products_web.get_product_name(request)
    suggested_product = await _try_show_login_fallbacks_on_wrong_password(
        request.app, user_id=user_id, product_name=product_name
    )
    if suggested_product:
        msg = MSG_WRONG_PASSWORD_MERGED_ACCOUNTS.format(suggested_product=suggested_product)

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
