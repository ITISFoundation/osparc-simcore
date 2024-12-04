import logging

from servicelib.aiohttp import status

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from .errors import LicenseGoodNotFoundError

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    LicenseGoodNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Market item {license_good_id} not found.",
    )
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
