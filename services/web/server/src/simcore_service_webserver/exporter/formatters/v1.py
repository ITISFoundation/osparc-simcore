import logging
import datetime
import json


from itertools import chain
from collections import deque
from typing import Deque
from collections import namedtuple
from pathlib import Path
from aiohttp import web

from .base import BaseFormatter

from ..serialize import loads, dumps
from ..file_downloader import ParallelDownloader

from simcore_service_webserver.projects.projects_api import get_project_for_user
from simcore_service_webserver.storage_handlers import (
    get_file_download_url,
    get_project_files_metadata,
)
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

    s3_metadata = await get_project_files_metadata(
        app=app,
        location_id="0",
        uuid_filter=project_id,
        user_id=user_id,
    )
    log.info("s3 files metadata %s: ", s3_metadata)

    blackfynn_metadata = await get_project_files_metadata(
        app=app,
        location_id="1",
        uuid_filter=project_id,
        user_id=user_id,
    )
    log.info("blackfynn files metadata %s: ", blackfynn_metadata)

    for file_metadata in chain(s3_metadata, blackfynn_metadata):
        download_link = await get_file_download_url(
            app=app,
            location_id=file_metadata["location_id"],
            fileId=file_metadata["raw_file_path"],
            user_id=user_id,
        )
        save_path = Path(file_metadata["location_id"]) / file_metadata["raw_file_path"]
        download_links.append(LinkAndPath(link=download_link, path=str(save_path)))

    await download_files(download_links=download_links, storage_path=storage_path)

    # TODO: maybe move this to a Pydantic model
    manifest = {
        "version": EXPORT_VERSION,
        "creation_date_utc": format_datetime(datetime.datetime.utcnow()),
    }

    manifest_path.write_text(dumps(manifest))
    pure_dict_project_data = json.loads(json.dumps(project_data))
    # TODO: move this to a Pydantic model
    project_path.write_text(dumps(pure_dict_project_data))


class FormatterV1(BaseFormatter):
    def __init__(self, root_folder: Path):
        super().__init__(version="1", root_folder=root_folder)

    async def format_export_directory(self, *args, **kwargs):
        # write manifest function
        app: web.Application = kwargs["app"]
        project_id: str = kwargs["project_id"]
        user_id: int = kwargs["user_id"]

        await generate_directory_contents(
            app=app, dir_path=self.root_folder, project_id=project_id, user_id=user_id
        )

    async def validate_and_import_directory(self, *args, **kwargs):
        user_id: int = kwargs["user_id"]

        projects_path = self.root_folder / "project.yaml"
        storage_path = self.root_folder / "storage"

        if not projects_path.is_file():
            raise web.HTTPException(
                reason=f"File {str(projects_path)} was not found in archive"
            )

        if not storage_path.is_dir():
            raise web.HTTPException(
                reason=f"Directory {str(storage_path)} was not found in archive"
            )

        project_data = loads(projects_path.read_text())
        log.info("Loaded project data: %s", project_data)
