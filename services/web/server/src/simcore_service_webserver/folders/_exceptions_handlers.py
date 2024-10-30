import functools
import logging

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

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


def handle_plugin_requests_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except (FolderNotFoundError, WorkspaceNotFoundError) as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except (
            FolderAccessForbiddenError,
            WorkspaceAccessForbiddenError,
            WorkspaceFolderInconsistencyError,
        ) as exc:
            raise web.HTTPForbidden(reason=f"{exc}") from exc

        except (FolderValueNotPermittedError, FoldersValueError) as exc:
            raise web.HTTPBadRequest(reason=f"{exc}") from exc

    return wrapper
