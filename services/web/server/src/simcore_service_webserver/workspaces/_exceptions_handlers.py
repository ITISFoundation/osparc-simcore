import logging

from servicelib.aiohttp import status

from ..exceptions_handlers import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    create_exception_handlers_decorator,
)
from ..projects.exceptions import (
    BaseProjectError,
    ProjectRunningConflictError,
    ProjectStoppingError,
)
from .errors import (
    WorkspaceAccessForbiddenError,
    WorkspaceGroupNotFoundError,
    WorkspaceNotFoundError,
    WorkspacesValueError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    WorkspaceGroupNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Workspace {workspace_id} group {group_id} not found.",
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Does not have access to this workspace",
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Workspace not found. {reason}",
    ),
    # Trashing
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "One or more studies in this workspace are in use and cannot be trashed. Please stop all services first and try again",
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Something went wrong while stopping running services in studies within this workspace before trashing. Aborting trash.",
    ),
}


handle_plugin_requests_exceptions = create_exception_handlers_decorator(
    exceptions_catch=(BaseProjectError, WorkspacesValueError),
    exc_to_status_map=_TO_HTTP_ERROR_MAP,
)
