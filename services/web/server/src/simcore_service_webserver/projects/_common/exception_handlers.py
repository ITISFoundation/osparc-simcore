import logging

from servicelib.aiohttp import status

from ...exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ...folders.errors import FolderAccessForbiddenError, FolderNotFoundError
from ...workspaces.errors import WorkspaceAccessForbiddenError, WorkspaceNotFoundError
from ..exceptions import (
    ProjectDeleteError,
    ProjectInvalidRightsError,
    ProjectNotFoundError,
    ProjectOwnerNotFoundInTheProjectAccessRightsError,
    WrongTagIdsInQueryError,
)

_logger = logging.getLogger(__name__)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    #
    # NOTE: keep keys alphabetically sorted
    #
    FolderAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Access to folder forbidden",
    ),
    FolderNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Folder not found: {reason}",
    ),
    ProjectDeleteError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Failed to complete deletion of '{project_uuid}': {reason}",
    ),
    ProjectInvalidRightsError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Do not have sufficient access rights on project {project_uuid} for this action",
    ),
    ProjectNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Project not found",
    ),
    ProjectOwnerNotFoundInTheProjectAccessRightsError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Project owner identifier was not found in the project's access-rights field",
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Access to workspace forbidden: {reason}",
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Workspace not found: {reason}",
    ),
    WrongTagIdsInQueryError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        "Wrong tag IDs in query",
    ),
}

handle_plugin_requests_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)
