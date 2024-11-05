import logging

from servicelib.aiohttp import status

from ..exceptions_handlers import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    create_exception_handlers_decorator,
)
from ..projects.exceptions import (
    ProjectRunningConflictError,
    ProjectStoppingError,
    ProjectTrashError,
)
from ..workspaces.errors import (
    WorkspaceAccessForbiddenError,
    WorkspaceFolderInconsistencyError,
    WorkspaceNotFoundError,
)
from .errors import (
    FolderAccessForbiddenError,
    FolderNotFoundError,
    FoldersValueError,
    FolderValueNotPermittedError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    FolderNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Folder was not found",
    ),
    WorkspaceNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "Workspace was not found",
    ),
    FolderAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Does not have access to this folder",
    ),
    WorkspaceAccessForbiddenError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "Does not have access to this workspace",
    ),
    WorkspaceFolderInconsistencyError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        "This folder does not exist in this workspace",
    ),
    FolderValueNotPermittedError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Provided folder value is not permitted: {reason}",
    ),
    FoldersValueError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Invalid folder value set: {reason}",
    ),
    ProjectRunningConflictError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "One or more studies in this folder are in use and cannot be trashed. Please stop all services first and try again",
    ),
    ProjectStoppingError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Something went wrong while stopping services before trashing. Aborting trash.",
    ),
}


handle_plugin_requests_exceptions = create_exception_handlers_decorator(
    exception_catch=(ProjectTrashError, FoldersValueError),
    exc_to_status_map=_TO_HTTP_ERROR_MAP,
)
