import json
import logging
import traceback
from collections import deque
from datetime import datetime, timezone
from itertools import chain
from pathlib import Path
from typing import Deque, Optional
from uuid import UUID

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from models_library.api_schemas_storage import ETag, LinkType
from models_library.projects import AccessRights, Project
from models_library.projects_nodes_io import (
    BaseFileLink,
    LocationID,
    NodeID,
    NodeIDStr,
    StorageFileID,
)
from models_library.users import UserID
from models_library.utils.nodes import compute_node_hash, project_node_io_payload_cb
from pydantic import AnyUrl, parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from servicelib.utils import logged_gather
from simcore_sdk.node_ports_common.exceptions import (
    NodeportsException,
    S3InvalidPathError,
    StorageInvalidCall,
)
from simcore_sdk.node_ports_common.filemanager import (
    get_download_link_from_s3,
    upload_file,
)
from simcore_sdk.node_ports_common.storage_client import (
    get_storage_locations,
    list_file_metadata,
)

from ...director_v2_api import create_or_update_pipeline
from ...projects.projects_api import get_project_for_user, submit_delete_project_task
from ...projects.projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from ...projects.projects_exceptions import ProjectsException
from ...users_api import get_user
from ...utils import now_str
from ..exceptions import ExporterException
from ..file_downloader import ParallelDownloader
from .base_formatter import BaseFormatter
from .models import LinkAndPath2, ManifestFile, ProjectFile, ShuffledData

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
    manifest_root_folder: Optional[Path],
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


async def upload_file_to_storage(
    link_and_path: LinkAndPath2,
    user_id: int,
    session: ClientSession,
) -> tuple[LinkAndPath2, ETag]:
    try:
        _, e_tag = await upload_file(
            user_id=user_id,
            store_id=link_and_path.storage_type,
            store_name=None,
            s3_object=link_and_path.relative_path_to_file,
            file_to_upload=link_and_path.storage_path_to_file,
            client_session=session,
            io_log_redirect_cb=None,
        )
        return (link_and_path, e_tag)
    except (
        NodeportsException,
        ClientError,
    ) as err:
        raise ExporterException(
            f"While requesting upload for '{link_and_path.relative_path_to_file}' "
            f"the following error occurred: {err}"
        ) from err


async def add_new_project(
    app: web.Application, project: Project, user_id: int, product_name: str
):
    # TODO: move this to projects_api
    # TODO: this piece was taking fromt the end of projects.projects_handlers.create_projects

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]

    # validated project is transform in dict via json to use only primitive types
    project_in: dict = json.loads(
        project.json(exclude_none=True, by_alias=True, exclude_unset=True)
    )

    # update metadata (uuid, timestamps, ownership) and save
    _project_db: dict = await db.insert_project(
        project_in, user_id, force_as_template=False, product_name=product_name
    )
    if _project_db["uuid"] != str(project.uuid):
        raise ExporterException("Project uuid dose nto match after validation")

    await create_or_update_pipeline(app, user_id, project.uuid)


async def _fix_node_run_hashes_based_on_old_project(
    project: Project, original_project: Project, node_mapping: ShuffledData
) -> None:
    for old_node_id, old_node in original_project.workbench.items():
        new_node_id = node_mapping.get(old_node_id)
        if new_node_id is None:
            # this should not happen
            log.warning("could not find new node id %s", new_node_id)
            continue
        new_node = project.workbench.get(parse_obj_as(NodeIDStr, f"{new_node_id}"))
        if new_node is None:
            # this should also not happen
            log.warning("could not find new node data from id %s", new_node_id)
            continue

        # check the node status in the old project
        old_computed_hash = await compute_node_hash(
            NodeID(old_node_id), project_node_io_payload_cb(original_project)
        )
        log.debug(
            "node %s old run hash: %s, computed old hash: %s",
            old_node_id,
            old_node.run_hash,
            old_computed_hash,
        )
        node_needs_update = old_computed_hash != old_node.run_hash
        # set the new node hash
        new_node.run_hash = (
            None
            if node_needs_update
            else await compute_node_hash(
                NodeID(new_node_id), project_node_io_payload_cb(project)
            )
        )


async def _fix_file_e_tags(
    project: Project, links_to_etags: list[tuple[LinkAndPath2, ETag]]
) -> None:
    for link_and_path, e_tag in links_to_etags:
        file_path = link_and_path.relative_path_to_file
        parts = link_and_path.relative_path_to_file.split("/")
        if len(parts) < 3:
            log.warning(
                "fixing eTag while importing issue: the path is not expected, skipping %s",
                file_path,
            )
            continue
        node_id = parts[-2]

        # now try to fix the eTag if any
        node = project.workbench.get(NodeIDStr(node_id))
        if node is None:
            log.warning(
                "node %s could not be found in project, skipping eTag fix",
                node_id,
            )
            continue
        # find the file in the outputs if any
        if node.outputs:
            for output in node.outputs.values():
                if isinstance(output, BaseFileLink) and output.path == str(file_path):
                    output.e_tag = e_tag


async def _remove_runtime_states(project: Project):
    for node_data in project.workbench.values():
        node_data.state = None


async def _upload_files_to_storage(
    user_id: int,
    root_folder: Path,
    manifest_file: ManifestFile,
    shuffled_data: ShuffledData,
) -> list[tuple[LinkAndPath2, ETag]]:
    # check all attachments are present
    client_timeout = ClientTimeout(  # type: ignore
        total=UPLOAD_HTTP_TIMEOUT, connect=None, sock_connect=5
    )
    async with ClientSession(timeout=client_timeout) as session:
        run_in_parallel = deque()
        for attachment in manifest_file.attachments:
            attachment_parts = attachment.split("/")
            link_and_path = LinkAndPath2(
                root_dir=root_folder,
                storage_type=parse_obj_as(LocationID, attachment_parts[0]),
                relative_path_to_file=parse_obj_as(
                    StorageFileID, "/".join(attachment_parts[1:])
                ),
                download_link=None,
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
                    link_and_path=link_and_path,
                    user_id=user_id,
                    session=session,
                )
            )
        links_to_new_e_tags = await logged_gather(*run_in_parallel, max_concurrency=2)

    return links_to_new_e_tags


async def import_files_and_validate_project(
    app: web.Application,
    user_id: int,
    product_name: str,
    root_folder: Path,
    manifest_root_folder: Optional[Path],
) -> str:
    project_file = await ProjectFile.model_from_file(root_dir=root_folder)
    shuffled_data: ShuffledData = project_file.get_shuffled_uuids()

    # replace shuffled_data in project
    # NOTE: there is no reason to write the shuffled data to file
    log.debug("Loaded project data:  %s", project_file)
    shuffled_project_file = project_file.new_instance_from_shuffled_data(
        shuffled_data=shuffled_data
    )
    # creating an unique name to help the user distinguish
    # between the original and new study
    shuffled_project_file.name = "{} {}".format(
        shuffled_project_file.name,
        datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y:%m:%d:%H:%M:%S"),
    )

    log.debug("Shuffled project data: %s", shuffled_project_file)

    # NOTE: it is not necessary to apply data shuffling to the manifest
    manifest_file = await ManifestFile.model_from_file(
        root_dir=manifest_root_folder or root_folder
    )

    user: dict = await get_user(app=app, user_id=user_id)

    # create and add the project
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
        quality=shuffled_project_file.quality,
    )
    project_uuid = str(project.uuid)

    try:
        await _remove_runtime_states(project)
        await add_new_project(app, project, user_id, product_name)

        # upload files to storage
        links_to_new_e_tags = await _upload_files_to_storage(
            user_id=user_id,
            root_folder=root_folder,
            manifest_file=manifest_file,
            shuffled_data=shuffled_data,
        )
        # fix etags
        await _fix_file_e_tags(project, links_to_new_e_tags)
        # NOTE: first fix the file eTags, and then the run hashes
        await _fix_node_run_hashes_based_on_old_project(
            project, project_file, shuffled_data
        )
    except Exception as e:
        log.warning(
            "The below error occurred during import\n%s", traceback.format_exc()
        )
        log.warning(
            "Removing project %s, because there was an error while importing it."
        )
        try:
            await submit_delete_project_task(
                app=app, project_uuid=UUID(project_uuid), user_id=user_id
            )
        except ProjectsException:
            # no need to raise an error here
            log.exception(
                "Could not find project %s while trying to revert actions", project_uuid
            )
        raise e

    return project_uuid


class FormatterV1(BaseFormatter):
    def __init__(self, root_folder: Path, version: str = "1"):
        super().__init__(version=version, root_folder=root_folder)

    async def format_export_directory(
        self, app: web.Application, project_id: str, user_id: int, **kwargs
    ) -> None:
        # injected by Formatter_V2
        manifest_root_folder: Optional[Path] = kwargs.get("manifest_root_folder")

        await generate_directory_contents(
            app=app,
            root_folder=self.root_folder,
            manifest_root_folder=manifest_root_folder,
            project_id=project_id,
            user_id=user_id,
            version=self.version,
        )

    async def validate_and_import_directory(self, **kwargs) -> str:
        app: web.Application = kwargs["app"]
        user_id: int = kwargs["user_id"]
        product_name: str = kwargs["product_name"]
        # injected by Formatter_V2
        manifest_root_folder: Optional[Path] = kwargs.get("manifest_root_folder")

        return await import_files_and_validate_project(
            app=app,
            user_id=user_id,
            product_name=product_name,
            root_folder=self.root_folder,
            manifest_root_folder=manifest_root_folder,
        )
