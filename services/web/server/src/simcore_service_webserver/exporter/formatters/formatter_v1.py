import asyncio
import json
import logging
import traceback
from collections import deque
from itertools import chain
from pathlib import Path
from typing import Deque, Dict

import aiofiles
from aiohttp import ClientSession, ClientTimeout, web
from models_library.projects import AccessRights, Project
from simcore_service_webserver.director_v2 import create_or_update_pipeline
from simcore_service_webserver.projects.projects_api import (
    delete_project,
    get_project_for_user,
)
from simcore_service_webserver.projects.projects_db import APP_PROJECT_DBAPI
from simcore_service_webserver.projects.projects_exceptions import ProjectsException
from simcore_service_webserver.storage_handlers import (
    get_file_download_url,
    get_file_upload_url,
    get_project_files_metadata,
)
from simcore_service_webserver.users_api import get_user
from simcore_service_webserver.utils import now_str

from ..exceptions import ExporterException
from ..file_downloader import ParallelDownloader
from ..utils import path_getsize
from .base_formatter import BaseFormatter
from .models import LinkAndPath2, ManifestFile, ProjectFile, ShuffledData

UPLOAD_HTTP_TIMEOUT = 60 * 60  # 1 hour

log = logging.getLogger(__name__)


async def download_all_files_from_storage(
    app: web.Application, download_links: Deque[LinkAndPath2]
) -> None:
    """ Downloads links to files in their designed storage_path_to_file """
    parallel_downloader = ParallelDownloader()
    for link_and_path in download_links:
        log.debug(
            "Will download %s -> '%s'",
            link_and_path.download_link,
            link_and_path.storage_path_to_file,
        )
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
    app: web.Application, dir_path: Path, project_id: str, user_id: int
) -> Deque[LinkAndPath2]:
    download_links: Deque[LinkAndPath2] = deque()

    s3_metadata = await get_project_files_metadata(
        app=app,
        location_id="0",
        uuid_filter=project_id,
        user_id=user_id,
    )
    log.debug("s3 files metadata %s: ", s3_metadata)

    # Still not sure if these are required, when pulling files from blackfynn they end up in S3
    # I am not sure there is an example where we need to directly export form blackfynn
    blackfynn_metadata = await get_project_files_metadata(
        app=app,
        location_id="1",
        uuid_filter=project_id,
        user_id=user_id,
    )
    log.debug("blackfynn files metadata %s: ", blackfynn_metadata)

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
    app: web.Application, root_folder: Path, project_id: str, user_id: int, version: str
) -> None:
    try:
        project_data = await get_project_for_user(
            app=app,
            project_uuid=project_id,
            user_id=user_id,
            include_templates=True,
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
    await ManifestFile.model_to_file(root_dir=root_folder, **manifest_params)

    # store project data on disk
    await ProjectFile.model_to_file(root_dir=root_folder, **project_data)


async def upload_file_to_storage(
    app: web.Application,
    link_and_path: LinkAndPath2,
    user_id: int,
    session: ClientSession,
) -> None:
    upload_url = await get_file_upload_url(
        app=app,
        location_id=str(link_and_path.storage_type),
        fileId=str(link_and_path.relative_path_to_file),
        user_id=user_id,
    )
    log.debug(">>> upload url >>> %s", upload_url)

    async def file_sender(file_name=None):
        async with aiofiles.open(file_name, "rb") as f:
            chunk = await f.read(64 * 1024)
            while chunk:
                yield chunk
                chunk = await f.read(64 * 1024)

    data_provider = file_sender(file_name=link_and_path.storage_path_to_file)
    content_size = await path_getsize(link_and_path.storage_path_to_file)
    headers = {"Content-Length": str(content_size)}
    async with session.put(upload_url, data=data_provider, headers=headers) as resp:
        upload_result = await resp.text()
        if resp.status != 200:
            raise ExporterException(
                f"Client replied with status={resp.status} and body '{upload_result}'"
            )

        log.debug("Upload status=%s, result: '%s'", resp.status, upload_result)


async def add_new_project(app: web.Application, project: Project, user_id: int):
    # TODO: move this to projects_api
    # TODO: this piece was taking fromt the end of projects.projects_handlers.create_projects

    db = app[APP_PROJECT_DBAPI]

    # validated project is transform in dict via json to use only primitive types
    project_in: Dict = json.loads(project.json(exclude_none=True, by_alias=True))

    # update metadata (uuid, timestamps, ownership) and save
    _project_db: Dict = await db.add_project(
        project_in, user_id, force_as_template=False
    )
    if _project_db["uuid"] != str(project.uuid):
        raise ExporterException("Project uuid dose nto match after validation")

    await create_or_update_pipeline(app, user_id, project.uuid)


async def import_files_and_validate_project(
    app: web.Application, user_id: int, root_folder: Path
) -> str:
    project_file = await ProjectFile.model_from_file(root_dir=root_folder)
    shuffled_data: ShuffledData = project_file.get_shuffled_uuids()

    # replace shuffled_data in project
    # NOTE: there is no reason to write the shuffled data to file
    log.debug("Loaded project data:  %s", project_file)
    shuffled_project_file = project_file.new_instance_from_shuffled_data(
        shuffled_data=shuffled_data
    )

    log.debug("Shuffled project data: %s", shuffled_project_file)

    # NOTE: it is not necessary to apply data shuffling to the manifest
    manifest_file = await ManifestFile.model_from_file(root_dir=root_folder)

    user: Dict = await get_user(app=app, user_id=user_id)

    # check all attachments are present
    client_timeout = ClientTimeout(total=UPLOAD_HTTP_TIMEOUT, connect=5, sock_connect=5)
    async with ClientSession(timeout=client_timeout) as session:
        run_in_parallel = deque()
        for attachment in manifest_file.attachments:
            attachment_parts = attachment.split("/")
            link_and_path = LinkAndPath2(
                root_dir=root_folder,
                storage_type=attachment_parts[0],
                relative_path_to_file="/".join(attachment_parts[1:]),
                download_link="",
            )
            # check file exists
            if not await link_and_path.is_file():
                raise ExporterException(
                    f"Could not find {link_and_path.storage_path_to_file} in import document"
                )
            # apply shuffle data which will move the file and check again it exits
            await link_and_path.apply_shuffled_data(shuffled_data=shuffled_data)
            if not await link_and_path.is_file():
                raise ExporterException(
                    f"Could not find {link_and_path.storage_path_to_file} after shuffling data"
                )

            run_in_parallel.append(
                upload_file_to_storage(
                    app=app,
                    link_and_path=link_and_path,
                    user_id=user_id,
                    session=session,
                )
            )
        await asyncio.gather(*run_in_parallel)

    # finally create and add the project
    project = Project(
        uuid=shuffled_project_file.uuid,
        name=shuffled_project_file.name,
        description=shuffled_project_file.description,
        thumbnail=shuffled_project_file.thumbnail,
        prjOwner=user["email"],
        accessRights={
            user["primary_gid"]: AccessRights(read=True, write=True, delete=True)
        },
        creationDate=now_str(),
        lastChangeDate=now_str(),
        dev=shuffled_project_file.dev,
        workbench=shuffled_project_file.workbench,
        ui=shuffled_project_file.ui,
    )
    project_uuid = str(project.uuid)

    try:
        await add_new_project(app, project, user_id)
    except Exception as e:
        log.warning(
            "The below error occurred during import\n%s", traceback.format_exc()
        )
        log.warning(
            "Removing project %s, because there was an error while importing it."
        )
        try:
            await delete_project(app=app, project_uuid=project_uuid, user_id=user_id)
        except ProjectsException as e:
            # no need to raise an error here
            log.exception(
                "Could not find project %s while trying to revert actions", project_uuid
            )
        raise e

    return project_uuid


class FormatterV1(BaseFormatter):
    def __init__(self, root_folder: Path):
        super().__init__(version="1", root_folder=root_folder)

    async def format_export_directory(self, **kwargs) -> None:
        app: web.Application = kwargs["app"]
        project_id: str = kwargs["project_id"]
        user_id: int = kwargs["user_id"]

        await generate_directory_contents(
            app=app,
            root_folder=self.root_folder,
            project_id=project_id,
            user_id=user_id,
            version=self.version,
        )

    async def validate_and_import_directory(self, **kwargs) -> str:
        app: web.Application = kwargs["app"]
        user_id: int = kwargs["user_id"]

        return await import_files_and_validate_project(
            app=app, user_id=user_id, root_folder=self.root_folder
        )
