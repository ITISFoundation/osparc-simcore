import logging

from servicelib.aiohttp import status
from simcore_service_webserver.wallets.errors import WalletAccessForbiddenError

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..wallets.errors import WalletNotEnoughCreditsError
from .errors import LicensedItemNotFoundError, LicensedItemPricingPlanMatchError

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    LicensedItemNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Market item {licensed_item_id} not found.",
    ),
    WalletAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Wallet {wallet_id} forbidden.",
    ),
    WalletNotEnoughCreditsError: HttpErrorInfo(
        status.HTTP_402_PAYMENT_REQUIRED,
        "Not enough credits in the wallet.",
    ),
    LicensedItemPricingPlanMatchError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "The provided pricing plan does not match the one associated with the licensed item.",
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
