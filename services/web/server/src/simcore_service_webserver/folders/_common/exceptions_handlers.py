import logging

from common_library.user_messages import user_message
from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...projects.exceptions import (
    ProjectInvalidRightsError,
    ProjectRunningConflictError,
    ProjectStoppingError,
)
from ...workspaces.errors import (
    WorkspaceAccessForbiddenError,
    WorkspaceFolderInconsistencyError,
    WorkspaceNotFoundError,
)
from ..errors import (
    FolderAccessForbiddenError,
    FolderNotFoundError,
    FoldersValueError,
    FolderValueNotPermittedError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    FolderNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested folder could not be found.", _version=1),
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("The requested workspace could not be found.", _version=1),
    ),
    FolderAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("You do not have permission to access this folder.", _version=1),
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "You do not have permission to access this workspace.", _version=1
        ),
    ),
    WorkspaceFolderInconsistencyError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "This folder is not available in the selected workspace.", _version=1
        ),
    ),
    FolderValueNotPermittedError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message("The folder operation cannot be completed: {reason}", _version=1),
    ),
    FoldersValueError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message("The folder configuration is invalid: {reason}", _version=1),
    ),
    ProjectInvalidRightsError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "You do not have permission to move the project with UUID: {project_uuid}. To locate this project, copy and paste the UUID into the search bar.",
            _version=1,
        ),
    ),
    # Trashing
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "Cannot move folder to trash because it contains projects that are currently running. Please stop all running services first and try again.",
            _version=2,
        ),
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "Something went wrong while stopping running services in projects within this folder before trashing. Aborting trash.",
            _version=2,
        ),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
# this is one decorator with a single exception handler
