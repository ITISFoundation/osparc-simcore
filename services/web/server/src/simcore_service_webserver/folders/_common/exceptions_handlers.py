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
        user_message("Folder was not found"),
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Workspace was not found"),
    ),
    FolderAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("Does not have access to this folder"),
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("Does not have access to this workspace"),
    ),
    WorkspaceFolderInconsistencyError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("This folder does not exist in this workspace"),
    ),
    FolderValueNotPermittedError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message("Provided folder value is not permitted: {reason}"),
    ),
    FoldersValueError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message("Invalid folder value set: {reason}"),
    ),
    ProjectInvalidRightsError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Access Denied: You do not have permission to move the project with UUID: {project_uuid}. Tip: Copy and paste the UUID into the search bar to locate the project."
        ),
    ),
    # Trashing
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "One or more studies in this folder are in use and cannot be trashed. Please stop all services first and try again"
        ),
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "Something went wrong while stopping running services in studies within this folder before trashing. Aborting trash."
        ),
    ),
}


handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
# this is one decorator with a single exception handler
