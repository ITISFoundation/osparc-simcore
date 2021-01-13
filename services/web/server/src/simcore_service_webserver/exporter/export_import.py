import logging
from pathlib import Path

import aiofiles
from aiohttp import web
from aiohttp.web_request import FileField
from simcore_service_webserver.studies_dispatcher._users import UserInfo

from .archiving import unzip_folder, validate_osparc_import_name, zip_folder
from .async_hashing import checksum
from .exceptions import ExporterException
from .formatters import BaseFormatter, FormatterV1, validate_manifest

log = logging.getLogger(__name__)


async def study_export(
    app: web.Application,
    tmp_dir: str,
    project_id: str,
    user_id: int,
    archive: bool = False,
    compress: bool = False,
) -> Path:
    """
    Generates a folder with all the data necessary for exporting a project.
    If compress is True, an archive will always be produced.

    returns:
        directory: if both archive and compress are False
        uncompressed archive: if archive is True and compress is False
        compressed archive: if both archive and compress are True
    """
    # storage area for the project data
    destination = Path(tmp_dir) / project_id
    destination.mkdir(parents=True, exist_ok=True)

    # The formatter will always be chosen to be the highest availabel version
    formatter = FormatterV1(root_folder=destination)
    await formatter.format_export_directory(
        app=app, project_id=project_id, user_id=user_id
    )

    if archive is False and compress is False:
        # returns the path to the temporary directory containing the study data
        return destination

    if archive and compress is False:
        archive_path = await zip_folder(
            project_id=project_id, input_path=destination, no_compression=True
        )
        return archive_path

    # an archive is always produced when compression is active
    # compress is always True in this situation
    archive_path = await zip_folder(
        project_id=project_id, input_path=destination, no_compression=False
    )

    return archive_path


async def study_import(
    app: web.Application,
    temp_dir: str,
    file_field: FileField,
    user: UserInfo,
    chunk_size: int = 2 ** 16,
) -> str:
    """
    Creates a project from a given exported project and returns
    the imported project's uuid.
    """
    # Storing file to disk
    upload_file_name = Path(temp_dir) / "uploaded.zip"
    # upload and verify checksum
    original_file_name = file_field.filename

    async with aiofiles.open(upload_file_name, mode="wb") as file_descriptor:
        while True:
            chunk = file_field.file.read(chunk_size)
            if not chunk:
                break

            await file_descriptor.write(chunk)

    log.debug(
        "original_file_name=%s, upload_file_name=%s",
        original_file_name,
        str(upload_file_name),
    )

    # compute_checksup and check if they match
    algorithm, digest_from_filename = validate_osparc_import_name(original_file_name)
    upload_digest = await checksum(file_path=upload_file_name, algorithm=algorithm)
    if digest_from_filename != upload_digest:
        raise ExporterException(
            "Upload error. Digests did not match digest_from_filename="
            f"{digest_from_filename}, upload_digest={upload_digest}"
        )

    unzipped_root_folder = await unzip_folder(upload_file_name)

    formatter: BaseFormatter = await validate_manifest(unzipped_root_folder)
    return await formatter.validate_and_import_directory(app=app, user=user)
