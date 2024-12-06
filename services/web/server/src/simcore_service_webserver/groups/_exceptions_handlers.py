import logging

from servicelib.aiohttp import status

from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..users.exceptions import UserNotFoundError
from .exceptions import (
    GroupNotFoundError,
    UserAlreadyInGroupError,
    UserInGroupNotFoundError,
    UserInsufficientRightsError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    UserNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "User {uid} or {email} not found",
    ),
    GroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Group {gid} not found",
    ),
    UserInGroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "User not found in group {gid}",
    ),
    UserAlreadyInGroupError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "User is already in group {gid}",
    ),
    UserInsufficientRightsError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Insufficient rights for {permission} access to group {gid}",
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
# this is one decorator with a single exception handler
