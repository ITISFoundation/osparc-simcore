import logging
from collections import deque
from itertools import chain
from pathlib import Path
from typing import Deque

from aiohttp import ClientError, web
from models_library.api_schemas_storage import LinkType
from models_library.users import UserID
from pydantic import AnyUrl, parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from servicelib.utils import logged_gather
from simcore_sdk.node_ports_common.exceptions import (
    S3InvalidPathError,
    StorageInvalidCall,
)
from simcore_sdk.node_ports_common.filemanager import get_download_link_from_s3
from simcore_sdk.node_ports_common.storage_client import (
    get_storage_locations,
    list_file_metadata,
)

from ...projects.projects_api import get_project_for_user
from ...projects.projects_exceptions import ProjectsException
from ..exceptions import ExporterException
from ..file_downloader import ParallelDownloader
from .base_formatter import BaseFormatter
from .models import LinkAndPath2, ManifestFile, ProjectFile

UPLOAD_HTTP_TIMEOUT = 60 * 60  # 1 hour

log = logging.getLogger(__name__)


async def download_all_files_from_storage(
    app: web.Application, download_links: Deque[LinkAndPath2]
) -> None:
    """Downloads links to files in their designed storage_path_to_file"""
    parallel_downloader = ParallelDownloader()
    for link_and_path in download_links:
        log.debug(
            "Will download %s -> '%s'",
            link_and_path.download_link,
            link_and_path.storage_path_to_file,
        )
        assert link_and_path.download_link  # nosec
        await parallel_downloader.append_file(
            link=link_and_path.download_link,
            download_path=link_and_path.storage_path_to_file,
        )

    await parallel_downloader.download_files(app)

    # check all files have been downloaded
    for link_and_path in download_links:
        if not await link_and_path.is_file():
            raise ExporterException(
                f"Could not download file {link_and_path.download_link} "
                f"to {link_and_path.storage_path_to_file}"
            )


async def extract_download_links(
    app: web.Application, dir_path: Path, project_id: str, user_id: UserID
) -> Deque[LinkAndPath2]:
    download_links: Deque[LinkAndPath2] = deque()
    try:
        session = get_client_session(app)
        file_locations = await get_storage_locations(session=session, user_id=user_id)
        log.debug(
            "will create download links for following locations: %s",
            file_locations.json(),
        )

        all_file_metadata = await logged_gather(
            *[
                list_file_metadata(
                    session=session,
                    location_id=loc.id,
                    uuid_filter=project_id,
                    user_id=user_id,
                )
                for loc in file_locations
            ],
            max_concurrency=2,
        )
    except Exception as e:
        raise ExporterException(
            f"Error while requesting project files metadata for S3 for project {project_id}"
        ) from e

    log.debug("files metadata %s: ", all_file_metadata)

    for file_metadata in chain.from_iterable(all_file_metadata):
        try:
            download_link = await get_download_link_from_s3(
                user_id=user_id,
                store_id=file_metadata.location_id,
                store_name=None,
                s3_object=file_metadata.file_id,
                link_type=LinkType.PRESIGNED,
                client_session=session,
            )
        except (S3InvalidPathError, StorageInvalidCall, ClientError) as e:
            raise ExporterException(
                f"Error while requesting download url for file {file_metadata.file_id}: {e}"
            ) from e
        download_links.append(
            LinkAndPath2(
                root_dir=dir_path,
                storage_type=file_metadata.location_id,
                relative_path_to_file=file_metadata.file_id,
                download_link=parse_obj_as(AnyUrl, f"{download_link}"),
            )
        )

    return download_links


async def generate_directory_contents(
    app: web.Application,
    root_folder: Path,
    manifest_root_folder: Path | None,
    project_id: str,
    user_id: int,
    version: str,
) -> None:
    try:
        project_data = await get_project_for_user(
            app=app,
            project_uuid=project_id,
            user_id=user_id,
            include_state=True,
        )
    except ProjectsException as e:
        raise ExporterException(f"Could not find project {project_id}") from e

    log.debug("Project data: %s", project_data)

    download_links: Deque[LinkAndPath2] = await extract_download_links(
        app=app, dir_path=root_folder, project_id=project_id, user_id=user_id
    )

    # make sure all files from storage services are persisted on disk
    await download_all_files_from_storage(app=app, download_links=download_links)

    # store manifest on disk
    manifest_params = dict(
        version=version,
        attachments=[str(x.store_path) for x in download_links],
    )
    await ManifestFile.model_to_file(
        root_dir=manifest_root_folder or root_folder, **manifest_params
    )

    # store project data on disk
    await ProjectFile.model_to_file(root_dir=root_folder, **project_data)


class FormatterV1(BaseFormatter):
    def __init__(self, root_folder: Path, version: str = "1"):
        super().__init__(version=version, root_folder=root_folder)

    async def format_export_directory(
        self, app: web.Application, project_id: str, user_id: int, **kwargs
    ) -> None:
        # injected by Formatter_V2
        manifest_root_folder: Path | None = kwargs.get("manifest_root_folder")

        await generate_directory_contents(
            app=app,
            root_folder=self.root_folder,
            manifest_root_folder=manifest_root_folder,
            project_id=project_id,
            user_id=user_id,
            version=self.version,
        )
