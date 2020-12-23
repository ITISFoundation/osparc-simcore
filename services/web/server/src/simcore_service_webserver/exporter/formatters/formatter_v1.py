import logging


from itertools import chain
from collections import deque
from typing import Deque
from pathlib import Path
from aiohttp import web

from .base_formatter import BaseFormatter
from .models import ManifestFile, ProjectFile, ShuffledData

from ..file_downloader import ParallelDownloader

from simcore_service_webserver.projects.projects_api import get_project_for_user
from simcore_service_webserver.storage_handlers import (
    get_file_download_url,
    get_project_files_metadata,
)

from .models import LinkAndPath2

log = logging.getLogger(__name__)


async def ensure_files_downloaded(download_links: Deque[LinkAndPath2]) -> None:
    """ Downloads links to files in their designed storage_path_to_file """
    # TODO: use utility
    parallel_downloader = ParallelDownloader()
    for link_and_path in download_links:
        log.info(
            "Will download %s -> '%s'",
            link_and_path.download_link,
            link_and_path.storage_path_to_file,
        )
        await parallel_downloader.append_file(
            link=link_and_path.download_link,
            download_path=link_and_path.storage_path_to_file,
        )

    await parallel_downloader.download_files()

    # check all files have been downloaded
    for link_and_path in download_links:
        if not link_and_path.is_file():
            raise web.HTTPException(
                reason=(
                    f"Could not download file {link_and_path.download_link} "
                    f"to {link_and_path.storage_path_to_file}"
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
        download_links.append(
            LinkAndPath2(
                root_dir=dir_path,
                storage_type=file_metadata["location_id"],
                relative_path_to_file=file_metadata["raw_file_path"],
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
        attachments=[str(x.store_path) for x in download_links],
    )
    await ManifestFile.model_to_file(root_dir=dir_path, **manifest_params)
    # store project data on disk
    project_params = project_data
    await ProjectFile.model_to_file(root_dir=dir_path, **project_params)


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

        project_file = await ProjectFile.model_from_file(root_dir=self.root_folder)
        shuffled_data: ShuffledData = project_file.get_shuffled_uuids()

        # replace shuffled_data in project
        # NOTE: there is no reason to write the shuffled data to file
        log.info("Loaded project data:  %s", project_file)
        shuffled_project_file = ProjectFile.replace_via_serialization(
            root_dir=self.root_folder, project=project_file, shuffled_data=shuffled_data
        )

        log.info("Shuffled project data: %s", shuffled_project_file)

        # check all attachments are present
        manifest_file = await ManifestFile.model_from_file(root_dir=self.root_folder)
        for attachment in manifest_file.attachments:
            attachment_parts = attachment.split("/")
            link_and_path = LinkAndPath2(
                root_dir=self.root_folder,
                storage_type=attachment_parts[0],
                relative_path_to_file="/".join(attachment_parts[1:]),
                download_link="",
            )
            # check file exists
            if not link_and_path.is_file():
                raise web.HTTPException(
                    reason=(
                        f"Could not find {link_and_path.download_link} in import document"
                    )
                )
            # apply shuffle data which will move the file and check again it exits
            await link_and_path.apply_shuffled_data(shuffled_data=shuffled_data)
            if not link_and_path.is_file():
                raise web.HTTPException(
                    reason=(
                        f"Could not find {link_and_path.download_link} after shuffling data"
                    )
                )
        # NOTE: it is not necessary to apply data shuffling to the manifest
        # TODO: import data after shuffling to the project
