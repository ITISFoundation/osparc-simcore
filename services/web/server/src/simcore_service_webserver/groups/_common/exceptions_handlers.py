import logging

from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...scicrunch.errors import InvalidRRIDError, ScicrunchError
from ...users.exceptions import UserNotFoundError
from ..exceptions import (
    GroupNotFoundError,
    UserAlreadyInGroupError,
    UserInGroupNotFoundError,
    UserInsufficientRightsError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    UserNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The user with ID {uid} or email {email} could not be found.", _version=1
        ),
    ),
    GroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The group with ID {gid} could not be found.", _version=1),
    ),
    UserInGroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The user is not a member of group {gid}.", _version=1),
    ),
    UserAlreadyInGroupError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message("The user is already a member of group {gid}.", _version=1),
    ),
    UserInsufficientRightsError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "You do not have sufficient rights for {permission} access to group {gid}.",
            _version=1,
        ),
    ),
    # scicrunch
    InvalidRRIDError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message("The RRID {rrid} is not valid.", _version=1),
    ),
    ScicrunchError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "Unable to retrieve RRID information because the scicrunch.org service is currently unavailable.",
            _version=1,
        ),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
# this is one decorator with a single exception handler
