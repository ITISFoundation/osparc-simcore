import logging

from aiohttp import web
from aiohttp.web_request import FileField

from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_decorators import permission_required
from .config import get_settings
from .exceptions import ExporterException
from .export_import import study_export, study_import
from .utils import CleanupFileResponse, get_empty_tmp_dir, remove_dir

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

    temp_dir: str = await get_empty_tmp_dir()

    try:
        file_to_download = await study_export(
            app=request.app,
            tmp_dir=temp_dir,
            project_id=project_uuid,
            user_id=user_id,
            archive=True,
        )
        log.info("File to download '%s'", file_to_download)

        if not file_to_download.is_file():
            raise ExporterException(
                f"Must provide a file to download, not {str(file_to_download)}"
            )
    except Exception as e:
        # make sure all errors are trapped and the directory where the file is sotred is removed
        await remove_dir(temp_dir)
        raise e

    headers = {"Content-Disposition": f'attachment; filename="{file_to_download.name}"'}

    return CleanupFileResponse(
        temp_dir=temp_dir, path=file_to_download, headers=headers
    )


@login_required
@permission_required("project.import")
async def import_project(request: web.Request):
    # bumping this requests's max size
    # pylint: disable=protected-access
    exporter_settings = get_settings(request.app)
    request._client_max_size = exporter_settings.max_upload_file_size * ONE_GB

    post_contents = await request.post()
    log.info("POST body %s", post_contents)
    user_id = request[RQT_USERID_KEY]
    file_name_field: FileField = post_contents.get("fileName", None)

    if file_name_field is None:
        raise ExporterException("Expected a file as 'fileName' form parmeter")
    if not isinstance(file_name_field, FileField):
        raise ExporterException("Please select a file")

    temp_dir: str = await get_empty_tmp_dir()

    imported_project_uuid = await study_import(
        app=request.app, temp_dir=temp_dir, file_field=file_name_field, user_id=user_id
    )
    await remove_dir(directory=temp_dir)

    return dict(uuid=imported_project_uuid)


rest_handler_functions = {fun.__name__: fun for fun in [export_project, import_project]}
