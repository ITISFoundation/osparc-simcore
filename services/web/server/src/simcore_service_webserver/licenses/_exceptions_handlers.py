import logging

from servicelib.aiohttp import status
from simcore_service_webserver.wallets.errors import WalletAccessForbiddenError

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from .errors import LicensedItemNotFoundError

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
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
