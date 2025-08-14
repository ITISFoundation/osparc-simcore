"""Defines the different exceptions that may arise in the catalog subpackage"""

import logging

from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..errors import (
    ConversationErrorNotFoundError,
    ConversationMessageErrorNotFoundError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    ConversationErrorNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "Conversation not found.",
            _version=1,
        ),
    ),
    ConversationMessageErrorNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "Conversation not found.",
            _version=1,
        ),
    ),
}


_handle_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
