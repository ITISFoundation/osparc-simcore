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
        user_message("Workspace {workspace_id} group {group_id} not found."),
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("Does not have access to this workspace"),
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Workspace not found. {reason}"),
    ),
    # Trashing
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "One or more studies in this workspace are in use and cannot be trashed. Please stop all services first and try again"
        ),
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "Something went wrong while stopping running services in studies within this workspace before trashing. Aborting trash."
        ),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
