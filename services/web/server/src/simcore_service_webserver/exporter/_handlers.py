import logging
from collections.abc import Callable, Coroutine
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from aiofiles.tempfile import TemporaryDirectory as AioTemporaryDirectory
from aiohttp import web
from models_library.projects_state import ProjectStatus
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG
from ..login.decorators import login_required
from ..projects.projects_api import with_project_locked_and_notify
from ..security.decorators import permission_required
from ..users.api import get_user_fullname
from ._formatter.archive import get_sds_archive_path
from .exceptions import SDSException
from .utils import CleanupFileResponse

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.post(f"/{API_VTAG}/projects/{{project_id}}:xport", name="export_project")
@login_required
@permission_required("project.export")
async def export_project(request: web.Request):
    """Exporting multiple studies in parallel is fully supported. How the process works:
    - each time an export request is created a new temporary
    directory is generated `/tmp/SOME_TMP_DIR/`
    - inside this directory a new directory is generated with the uuid of the
    project `/tmp/SOME_TMP_DIR/uuid/`.
    - All contents from the project are written inside the `/tmp/SOME_TMP_DIR/uuid/`
    directory (serialized data and storage files).
    - The `/tmp/SOME_TMP_DIR/uuid/` is zipped producing the archive to be downloaded
    in this path `/tmp/SOME_TMP_DIR/sds_PROJECT_ID.zip`
    - When the request finishes, for any reason (HTTP_OK, HTTP_ERROR, etc...), the
    `/tmp/SOME_TMP_DIR/` si removed from the disk."""
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    assert project_uuid  # nosec

    @with_project_locked_and_notify(
        request.app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        user_id=user_id,
        user_name=await get_user_fullname(request.app, user_id=user_id),
        notify_users=True,
    )
    async def _() -> tuple[Callable[[], Coroutine[Any, Any, None]], Path]:
        # @GitHK what is this supposed to be doing??
        async with AsyncExitStack() as tmp_dir_stack:
            tmp_dir = await tmp_dir_stack.enter_async_context(AioTemporaryDirectory())
            file_to_download = await get_sds_archive_path(
                app=request.app,
                tmp_dir=f"{tmp_dir}",
                project_id=project_uuid,
                user_id=user_id,
                product_name=request[RQ_PRODUCT_KEY],
            )
            _logger.info("File to download '%s'", file_to_download)

            if not file_to_download.is_file():
                msg = f"Must provide a file to download, not {file_to_download!s}"
                raise SDSException(msg)
            # this allows to transfer deletion of the tmp dir responsibility
        return tmp_dir_stack.pop_all().aclose, file_to_download

    delete_tmp_dir_callable, file_to_download = await _()

    headers = {"Content-Disposition": f'attachment; filename="{file_to_download.name}"'}
    assert delete_tmp_dir_callable  # nosec
    return CleanupFileResponse(
        remove_tmp_dir_cb=delete_tmp_dir_callable,
        path=file_to_download,
        headers=headers,
    )
