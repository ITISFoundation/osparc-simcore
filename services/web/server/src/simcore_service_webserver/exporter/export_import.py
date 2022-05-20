import logging
import urllib.parse
from pathlib import Path
from typing import Type

import aiofiles
from aiohttp import web
from aiohttp.web_request import FileField

from .archiving import unzip_folder, validate_osparc_import_name, zip_folder
from .async_hashing import checksum
from .exceptions import ExporterException
from .formatters import BaseFormatter, FormatterV2, validate_manifest

log = logging.getLogger(__name__)


async def study_export(
    app: web.Application,
    tmp_dir: str,
    project_id: str,
    user_id: int,
    product_name: str,
    archive: bool = False,
    formatter_class: Type[BaseFormatter] = FormatterV2,
) -> Path:
    """
    Generates a folder with all the data necessary for exporting a project.
    If archive is True, an archive will always be produced.

    returns: directory if archive is True else a compressed archive is returned
    """

    # storage area for the project data
    base_temp_dir = Path(tmp_dir)
    destination = base_temp_dir / project_id
    destination.mkdir(parents=True, exist_ok=True)

    # The formatter will always be chosen to be the highest availabel version
    formatter = formatter_class(root_folder=destination)
    await formatter.format_export_directory(
        app=app, project_id=project_id, user_id=user_id, product_name=product_name
    )

    if archive is False:
        # returns the path to the temporary directory containing the study data
        return destination

    # an archive is always produced when compression is active
    archive_path = await zip_folder(
        folder_to_zip=base_temp_dir, destination_folder=base_temp_dir
    )

    return archive_path


async def study_import(
    app: web.Application,
    temp_dir: str,
    file_field: FileField,
    user_id: int,
    chunk_size: int = 2**16,
) -> str:
    """
    Creates a project from a given exported project and returns
    the imported project's uuid.
    """
    # Storing file to disk
    base_temp_dir = Path(temp_dir)
    upload_file_name = base_temp_dir / "uploaded.zip"
    # upload and verify checksum
    original_file_name = urllib.parse.unquote(file_field.filename)

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

    # compute checksum and check if they match
    algorithm, digest_from_filename = validate_osparc_import_name(original_file_name)
    upload_digest = await checksum(file_path=upload_file_name, algorithm=algorithm)
    if digest_from_filename != upload_digest:
        raise ExporterException(
            "Upload error. Digests did not match digest_from_filename="
            f"{digest_from_filename}, upload_digest={upload_digest}"
        )

    unzipped_root_folder = await unzip_folder(
        archive_to_extract=upload_file_name, destination_folder=base_temp_dir
    )

    formatter: BaseFormatter = await validate_manifest(unzipped_root_folder)
    return await formatter.validate_and_import_directory(app=app, user_id=user_id)


async def study_duplicate(
    app: web.Application, user_id: int, exported_project_path: Path
) -> str:
    formatter: BaseFormatter = await validate_manifest(exported_project_path)
    return await formatter.validate_and_import_directory(app=app, user_id=user_id)
