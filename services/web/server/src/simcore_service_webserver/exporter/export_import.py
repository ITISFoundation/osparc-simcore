import logging
import datetime
import json
from pathlib import Path
from collections import deque, namedtuple
from typing import Deque

import aiofiles
from aiohttp import web
from aiohttp.web_request import FileField

from .archiving import zip_folder, validate_osparc_import_name, unzip_folder
from .file_downloader import ParallelDownloader
from .serialize import dumps, loads
from .async_hashing import checksum
from .importers import SUPPORTED_IMPORTERS_FROM_VERSION, BaseImporter

from simcore_service_webserver.projects.projects_api import get_project_for_user
from simcore_service_webserver.storage_handlers import get_file_download_url
from simcore_service_webserver.utils import format_datetime


log = logging.getLogger(__name__)

# used in the future, will change if export format changes
EXPORT_VERSION = "1"
KEYS_TO_VALIDATE = {"store", "path", "dataset", "label"}

LinkAndPath = namedtuple("LinkAndPath", ["link", "path"])


async def download_files(download_links: Deque[LinkAndPath], storage_path: Path):
    """ Downloads links to files in storage_path """
    # TODO: use utility
    parallel_downloader = ParallelDownloader()
    for link_and_path in download_links:
        download_path = storage_path / link_and_path.path
        log.info("Will download %s -> '%s'", link_and_path.link, download_path)
        await parallel_downloader.append_file(
            link=link_and_path.link, download_path=download_path
        )

    await parallel_downloader.download_files()


async def generate_directory_contents(
    app: web.Application, dir_path: Path, project_id: str, user_id: int
) -> None:
    manifest_path = dir_path / "manifest.yaml"
    project_path = dir_path / "project.yaml"
    storage_path = dir_path / "storage"

    project_data = await get_project_for_user(
        app=app,
        project_uuid=project_id,
        user_id=user_id,
        include_templates=True,
        include_state=True,
    )

    log.info("Project data: %s", project_data)

    download_links: Deque[LinkAndPath] = deque()

    workbench = project_data["workbench"]
    for node_data in workbench.values():
        outputs = node_data.get("outputs", {})
        for output in outputs.values():
            if not isinstance(output, dict):
                continue

            is_storage_file = KEYS_TO_VALIDATE <= output.keys()
            if not is_storage_file:
                log.warning(
                    "Expected a file from storage, the following format was provided %s",
                    output,
                )
                continue

            download_link = await get_file_download_url(
                app=app,
                location_id=output["store"],
                fileId=output["path"],
                user_id=user_id,
            )
            download_links.append(LinkAndPath(link=download_link, path=output["path"]))

    await download_files(download_links=download_links, storage_path=storage_path)

    # TODO: maybe move this to a Pydantic model
    manifest = {
        "version": EXPORT_VERSION,
        "creation_date_utc": format_datetime(datetime.datetime.utcnow()),
    }

    manifest_path.write_text(dumps(manifest))
    pure_dict_project_data = json.loads(json.dumps(project_data))
    project_path.write_text(dumps(pure_dict_project_data))


# neagu-wkst:9081/v0/projects/d3cfd554-3ed9-11eb-9dd5-02420a0000f6/export?compressed=true
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
    # acquire some random template
    # so the project model must use a from dict to dict serialization
    # also this should support options for zipping

    # storage area for the project data
    destination = Path(tmp_dir) / project_id
    destination.mkdir(parents=True, exist_ok=True)

    await generate_directory_contents(
        app=app, dir_path=destination, project_id=project_id, user_id=user_id
    )

    # at this point there is no more temp directory
    if archive is False and compress is False:
        # returns the path to the temporary directory containing the project
        return destination

    if archive and compress is False:
        archive_path = await zip_folder(
            project_id=project_id, input_path=destination, no_compression=True
        )
        return archive_path

    # an archive is always produced when compression is active
    # compress is always True in this situationå
    archive_path = await zip_folder(
        project_id=project_id, input_path=destination, no_compression=False
    )

    return archive_path


async def study_import(
    temp_dir: str, file_field: FileField, user_id: int, chunk_size: int = 2 ** 16
) -> None:
    """ Creates a project from a given exported project"""

    upload_file_name = Path(temp_dir) / "uploaded.zip"
    # upload and verify checksum
    original_file_name = file_field.filename

    async with aiofiles.open(upload_file_name, mode="wb") as file_descriptor:
        while True:
            chunk = file_field.file.read(chunk_size)
            if not chunk:
                break

            await file_descriptor.write(chunk)

    log.info(
        "original_file_name=%s, upload_file_name=%s",
        original_file_name,
        str(upload_file_name),
    )

    # compute_checksup and check if they match
    algorithm, digest_from_filename = validate_osparc_import_name(original_file_name)
    upload_digest = await checksum(file_path=upload_file_name, algorithm=algorithm)
    if digest_from_filename != upload_digest:
        raise web.HTTPException(
            reason=(
                "Upload error. Digests did not match digest_from_filename="
                f"{digest_from_filename}, upload_digest={upload_digest}"
            )
        )

    unzipped_root_folder = await unzip_folder(upload_file_name)
    # apply decoding based on format from manifest
    log.info("Will search in path %s", unzipped_root_folder)

    # dispatch to export version loader

    manifest = unzipped_root_folder / "manifest.yaml"

    if not manifest.is_file():
        raise web.HTTPException(
            reason="Expected a manifest.yaml file was not found in project"
        )

    manifest_data = loads(manifest.read_text())
    version = manifest_data.get("version", None)
    if version not in SUPPORTED_IMPORTERS_FROM_VERSION:
        raise web.HTTPException(
            reason=f"Version {version} was not found in {SUPPORTED_IMPORTERS_FROM_VERSION.keys()}"
        )

    importer_cls: BaseImporter = SUPPORTED_IMPORTERS_FROM_VERSION[version]
    importer = importer_cls(version=version, root_folder=unzipped_root_folder)

    # will start the import process
    await importer.start_import()
