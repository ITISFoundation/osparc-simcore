import logging

from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...wallets.errors import WalletAccessForbiddenError, WalletNotEnoughCreditsError
from ..errors import LicensedItemNotFoundError, LicensedItemPricingPlanMatchError

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    LicensedItemNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested market item '{licensed_item_id}' could not be found.",
            _version=1,
        ),
    ),
    WalletAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "You do not have permission to access credit account '{wallet_id}'.",
            _version=1,
        ),
    ),
    WalletNotEnoughCreditsError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        user_message(
            "Your credit account does not have sufficient funds to complete this purchase.",
            _version=1,
        ),
    ),
    LicensedItemPricingPlanMatchError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        user_message(
            "The selected pricing plan is not valid for this licensed item. Please choose a different plan.",
            _version=1,
        ),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
