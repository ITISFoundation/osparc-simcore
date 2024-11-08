import logging

from servicelib.aiohttp import status

from ..exceptions_handlers import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    create_exception_handlers_decorator,
)
from .errors import (
    WorkspaceAccessForbiddenError,
    WorkspaceGroupNotFoundError,
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
}


handle_plugin_requests_exceptions = create_exception_handlers_decorator(
    exceptions_catch=(WorkspacesValueError),
    exc_to_status_map=_TO_HTTP_ERROR_MAP,
)
