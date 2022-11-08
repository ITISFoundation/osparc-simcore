import logging
from contextlib import AsyncExitStack
from tempfile import TemporaryDirectory
from typing import Any, Callable, Coroutine, Optional

from aiofiles.tempfile import TemporaryDirectory as AioTemporaryDirectory
from aiohttp import web
from aiohttp.web_request import FileField
from models_library.projects_state import ProjectStatus

from .._constants import RQ_PRODUCT_KEY
from ..login.decorators import RQT_USERID_KEY, login_required
from ..projects.project_lock import lock_project
from ..projects.projects_api import retrieve_and_notify_project_locked_state
from ..security_decorators import permission_required
from ..users_api import get_user_name
from .exceptions import ExporterException
from .export_import import study_duplicate, study_export, study_import
from .formatters import FormatterV1
from .settings import get_plugin_settings
from .utils import CleanupFileResponse

ONE_GB: int = 1024 * 1024 * 1024

log = logging.getLogger(__name__)


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
    in this path `/tmp/SOME_TMP_DIR/some_name#SHA256=SOME_HASH.osparc`
    - When the request finishes, for any reason (HTTO_OK, HTTP_ERROR, etc...), the
    `/tmp/SOME_TMP_DIR/` si removed from the disk."""
    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    assert project_uuid  # nosec
    delete_tmp_dir: Optional[Callable[[], Coroutine[Any, Any, None]]] = None
    try:
        async with AsyncExitStack() as tmp_dir_stack, lock_project(
            request.app,
            project_uuid,
            ProjectStatus.EXPORTING,
            user_id,
            await get_user_name(request.app, user_id),
        ):
            await retrieve_and_notify_project_locked_state(
                user_id, project_uuid, request.app
            )
            tmp_dir = await tmp_dir_stack.enter_async_context(AioTemporaryDirectory())
            file_to_download = await study_export(
                app=request.app,
                tmp_dir=f"{tmp_dir}",
                project_id=project_uuid,
                user_id=user_id,
                product_name=request[RQ_PRODUCT_KEY],
                archive=True,
            )
            log.info("File to download '%s'", file_to_download)

            if not file_to_download.is_file():
                raise ExporterException(
                    f"Must provide a file to download, not {str(file_to_download)}"
                )
            # this allows to transfer deletion of the tmp dir responsibility
            delete_tmp_dir = tmp_dir_stack.pop_all().aclose
    finally:
        await retrieve_and_notify_project_locked_state(
            user_id, project_uuid, request.app
        )

    headers = {"Content-Disposition": f'attachment; filename="{file_to_download.name}"'}

    return CleanupFileResponse(
        remove_tmp_dir_cb=delete_tmp_dir, path=file_to_download, headers=headers
    )


@login_required
@permission_required("project.import")
async def import_project(request: web.Request):
    # bumping this requests's max size
    # pylint: disable=protected-access
    exporter_settings = get_plugin_settings(request.app)
    assert (  # nosec
        exporter_settings is not None
    ), "this call was not expected with a disabled plugin"  # nosec

    request._client_max_size = exporter_settings.EXPORTER_MAX_UPLOAD_FILE_SIZE * ONE_GB

    post_contents = await request.post()
    log.info("POST body %s", post_contents)
    user_id = request[RQT_USERID_KEY]
    product_name = request[RQ_PRODUCT_KEY]
    file_name_field: FileField = post_contents.get("fileName", None)

    if file_name_field is None:
        raise ExporterException("Expected a file as 'fileName' form parmeter")
    if not isinstance(file_name_field, FileField):
        raise ExporterException("Please select a file")

    async with AioTemporaryDirectory() as tmp_dir:
        imported_project_uuid = await study_import(
            app=request.app,
            temp_dir=f"{tmp_dir}",
            file_field=file_name_field,
            user_id=user_id,
            product_name=product_name,
        )

    return dict(uuid=imported_project_uuid)


@login_required
@permission_required("project.duplicate")
async def duplicate_project(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    product_name = request[RQ_PRODUCT_KEY]
    project_uuid = request.match_info.get("project_id")
    assert project_uuid  # nosec
    try:
        with TemporaryDirectory() as temp_dir:
            async with lock_project(
                request.app,
                project_uuid,
                ProjectStatus.CLONING,
                user_id,
                await get_user_name(request.app, user_id),
            ):
                await retrieve_and_notify_project_locked_state(
                    user_id, project_uuid, request.app
                )
                exported_project_path = await study_export(
                    app=request.app,
                    tmp_dir=temp_dir,
                    project_id=project_uuid,
                    user_id=user_id,
                    product_name=request[RQ_PRODUCT_KEY],
                    archive=False,
                    formatter_class=FormatterV1,
                )
                log.info("Study to duplicate '%s'", exported_project_path)

                # return the duplicated study ID
                duplicated_project_uuid = await study_duplicate(
                    app=request.app,
                    user_id=user_id,
                    product_name=product_name,
                    exported_project_path=exported_project_path,
                )
            return dict(uuid=duplicated_project_uuid)
    finally:
        await retrieve_and_notify_project_locked_state(
            user_id, project_uuid, request.app
        )


rest_handler_functions = {
    fun.__name__: fun for fun in {export_project, import_project, duplicate_project}
}
