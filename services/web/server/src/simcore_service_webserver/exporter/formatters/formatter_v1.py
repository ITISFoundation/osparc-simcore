import logging


from itertools import chain
from collections import deque
from typing import Deque
from pathlib import Path
from aiohttp import web

from .base_formatter import BaseFormatter
from .models import Manifest, Project

from ..file_downloader import ParallelDownloader

from simcore_service_webserver.projects.projects_api import get_project_for_user
from simcore_service_webserver.storage_handlers import (
    get_file_download_url,
    get_project_files_metadata,
)

from .models import LinkAndPath2

log = logging.getLogger(__name__)


async def ensure_files_downloaded(download_links: Deque[LinkAndPath2]) -> None:
    """ Downloads links to files in their designed store_path """
    # TODO: use utility
    parallel_downloader = ParallelDownloader()
    for link_and_path in download_links:
        log.info(
            "Will download %s -> '%s'",
            link_and_path.download_link,
            link_and_path.store_path,
        )
        await parallel_downloader.append_file(
            link=link_and_path.download_link, download_path=link_and_path.store_path
        )

    await parallel_downloader.download_files()

    # check all files have been downloaded
    for link_and_path in download_links:
        if not link_and_path.is_file():
            raise web.HTTPException(
                reason=(
                    f"Could not download file {link_and_path.download_link} "
                    f"to {link_and_path.store_path}"
                )
            )


async def extract_download_links(
    app: web.Application, dir_path: Path, project_id: str, user_id: int
) -> Deque[LinkAndPath2]:
    download_links: Deque[LinkAndPath2] = deque()

    s3_metadata = await get_project_files_metadata(
        app=app,
        location_id="0",
        uuid_filter=project_id,
        user_id=user_id,
    )
    log.info("s3 files metadata %s: ", s3_metadata)

    # Still not sure if these are required, when pulling files from blackfynn they end up in S3
    # I am not sure there is an example where we need to directly export form blackfynn
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
        download_links.append(
            LinkAndPath2(
                root_dir=dir_path,
                storage_path_to_file=str(save_path),
                download_link=download_link,
            )
        )

    return download_links


async def generate_directory_contents(
    app: web.Application, dir_path: Path, project_id: str, user_id: int, version: str
) -> None:
    project_data = await get_project_for_user(
        app=app,
        project_uuid=project_id,
        user_id=user_id,
        include_templates=True,
        include_state=True,
    )

    log.info("Project data: %s", project_data)

    download_links: Deque[LinkAndPath2] = await extract_download_links(
        app=app, dir_path=dir_path, project_id=project_id, user_id=user_id
    )

    # make sure all files from storage services are persisted on disk
    await ensure_files_downloaded(download_links=download_links)

    # store manifest on disk
    manifest_params = dict(
        version=version,
        attachments=[str(x.storage_path_to_file) for x in download_links],
    )
    await Manifest.model_to_file(root_dir=dir_path, **manifest_params)
    # store project data on disk
    project_params = project_data
    await Project.model_to_file(root_dir=dir_path, **project_params)


class FormatterV1(BaseFormatter):
    def __init__(self, root_folder: Path):
        super().__init__(version="1", root_folder=root_folder)

    async def format_export_directory(self, *args, **kwargs):
        # write manifest function
        app: web.Application = kwargs["app"]
        project_id: str = kwargs["project_id"]
        user_id: int = kwargs["user_id"]

        await generate_directory_contents(
            app=app,
            dir_path=self.root_folder,
            project_id=project_id,
            user_id=user_id,
            version=self.version,
        )

    async def validate_and_import_directory(self, *args, **kwargs):
        user_id: int = kwargs["user_id"]

        project = await Project.model_from_file(root_dir=self.root_folder)

        # check all attachments are present
        manifest = await Manifest.model_from_file(root_dir=self.root_folder)
        for attachment in manifest.attachments:
            link_and_path = LinkAndPath2(
                root_dir=self.root_folder,
                storage_path_to_file=attachment,
                download_link="",
            )
            if not link_and_path.is_file():
                raise web.HTTPException(
                    reason=(
                        f"Could not find {link_and_path.download_link} in import document"
                    )
                )

        log.info("Loaded project data: %s", project)


# TODO: create Pydantic models for:
#   - directory_storage_files
# TODO: models must switch uuid for project and nodes
