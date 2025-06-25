import logging

from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...projects.exceptions import ProjectRunningConflictError, ProjectStoppingError
from ..errors import (
    WorkspaceAccessForbiddenError,
    WorkspaceGroupNotFoundError,
    WorkspaceNotFoundError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    WorkspaceGroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested workspace {workspace_id} group {group_id} could not be found.",
            _version=1,
        ),
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "You do not have permission to access this workspace.", _version=1
        ),
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested workspace could not be found. {reason}", _version=1
        ),
    ),
    # Trashing
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "Unable to delete workspace because one or more projects are currently running. Please stop all running services and try again.",
            _version=1,
        ),
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "Something went wrong while stopping running services in projects within this workspace before trashing. Aborting trash.",
            _version=1,
        ),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
