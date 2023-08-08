import datetime
import logging
import tempfile
import urllib.parse
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from models_library.api_schemas_storage import LinkType, S3BucketName, UploadedPart
from models_library.projects import ProjectID
from models_library.projects_nodes_io import (
    LocationID,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, NonNegativeInt, parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.long_running_tasks.server import TaskProgress
from servicelib.utils import ensure_ends_with, logged_gather

from . import db_file_meta_data, db_projects, db_tokens
from .constants import (
    APP_CONFIG_KEY,
    APP_DB_ENGINE_KEY,
    DATCORE_ID,
    EXPAND_DIR_MAX_ITEM_COUNT,
    MAX_CONCURRENT_DB_TASKS,
    MAX_CONCURRENT_S3_TASKS,
    MAX_LINK_CHUNK_BYTE_SIZE,
    S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
    SIMCORE_S3_ID,
    SIMCORE_S3_STR,
)
from .datcore_adapter import datcore_adapter
from .db_access_layer import (
    AccessRights,
    get_file_access_rights,
    get_project_access_rights,
    get_readable_project_ids,
)
from .dsm_factory import BaseDataManager
from .exceptions import (
    FileAccessRightError,
    FileMetaDataNotFoundError,
    LinkAlreadyExistsError,
    ProjectAccessRightError,
    ProjectNotFoundError,
    S3KeyNotFoundError,
)
from .models import (
    DatasetMetaData,
    FileMetaData,
    FileMetaDataAtDB,
    UploadID,
    UploadLinks,
)
from .s3 import get_s3_client
from .s3_client import S3MetaData, StorageS3Client
from .s3_utils import S3TransferDataCB, update_task_progress
from .settings import Settings
from .simcore_s3_dsm_utils import (
    ensure_read_access_rights,
    expand_directory,
    get_directory_file_id,
    get_simcore_directory,
)
from .utils import (
    convert_db_to_model,
    download_to_file_or_raise,
    is_file_entry_valid,
    is_valid_managed_multipart_upload,
)

_MAX_PARALLEL_S3_CALLS: Final[NonNegativeInt] = 10
_MAX_ELEMENTS_TO_LIST: Final[int] = 1000

logger = logging.getLogger(__name__)


@dataclass
class SimcoreS3DataManager(BaseDataManager):
    engine: Engine
    simcore_bucket_name: S3BucketName
    app: web.Application
    settings: Settings

    @classmethod
    def get_location_id(cls) -> LocationID:
        return SIMCORE_S3_ID

    @classmethod
    def get_location_name(cls) -> str:
        return SIMCORE_S3_STR

    async def authorized(self, _user_id: UserID) -> bool:
        return True  # always true for now

    async def list_datasets(self, user_id: UserID) -> list[DatasetMetaData]:
        async with self.engine.acquire() as conn:
            readable_projects_ids = await get_readable_project_ids(conn, user_id)
            return [
                DatasetMetaData(
                    dataset_id=prj_data.uuid,
                    display_name=prj_data.name,
                )
                async for prj_data in db_projects.list_valid_projects_in(
                    conn, readable_projects_ids
                )
            ]

    async def list_files_in_dataset(
        self, user_id: UserID, dataset_id: str, *, expand_dirs: bool
    ) -> list[FileMetaData]:
        # NOTE: expand_dirs will be replaced by pagination in the future
        data: list[FileMetaData] = await self.list_files(
            user_id,
            expand_dirs=expand_dirs,
            uuid_filter=ensure_ends_with(dataset_id, "/"),
        )
        return data

    async def list_files(  # noqa C901
        self, user_id: UserID, *, expand_dirs: bool, uuid_filter: str = ""
    ) -> list[FileMetaData]:
        """
        expand_dirs `False`: returns one metadata entry for each directory
        expand_dirs `True`: returns all files in each directory (no directories will be included)

        NOTE: expand_dirs will be replaced by pagination in the future
        currently only {EXPAND_DIR_MAX_ITEM_COUNT} items will be returned
        The endpoint produces similar results to what it did previously
        """

        data: list[FileMetaData] = []
        accessible_projects_ids = []
        async with self.engine.acquire() as conn, conn.begin():
            accessible_projects_ids = await get_readable_project_ids(conn, user_id)
            file_and_directory_meta_data: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_filter_with_partial_file_id(
                conn,
                user_id=user_id,
                project_ids=accessible_projects_ids,
                file_id_prefix=None,
                partial_file_id=uuid_filter,
                only_files=False,
            )

            # add all the entries from file_meta_data without
            for metadata in file_and_directory_meta_data:
                # below checks ensures that directoris either appear as
                if metadata.is_directory and expand_dirs:
                    # avoids directory files and does not add any directory entry to the result
                    continue

                if is_file_entry_valid(metadata):
                    data.append(convert_db_to_model(metadata))
                    continue
                with suppress(S3KeyNotFoundError):
                    # 1. this was uploaded using the legacy file upload that relied on
                    # a background task checking the S3 backend unreliably, the file eventually
                    # will be uploaded and this will lazily update the database
                    # 2. this is still in upload and the file is missing and it will raise
                    updated_fmd = await self._update_database_from_storage(
                        conn, metadata
                    )
                    data.append(convert_db_to_model(updated_fmd))

            # try to expand directories the max number of files to return was not reached
            for metadata in file_and_directory_meta_data:
                if (
                    expand_dirs
                    and metadata.is_directory
                    and len(data) < EXPAND_DIR_MAX_ITEM_COUNT
                ):
                    max_items_to_include = EXPAND_DIR_MAX_ITEM_COUNT - len(data)
                    data.extend(
                        await expand_directory(
                            self.app,
                            self.simcore_bucket_name,
                            metadata,
                            max_items_to_include,
                        )
                    )

            # now parse the project to search for node/project names
            prj_names_mapping: dict[ProjectID | NodeID, str] = {}
            async for proj_data in db_projects.list_valid_projects_in(
                conn, accessible_projects_ids
            ):
                prj_names_mapping |= {proj_data.uuid: proj_data.name} | {
                    NodeID(node_id): node_data.label
                    for node_id, node_data in proj_data.workbench.items()
                }

        # FIXME: artifically fills ['project_name', 'node_name', 'file_id', 'raw_file_path', 'display_file_path']
        #        with information from the projects table!
        # also all this stuff with projects should be done in the client code not here
        # NOTE: sorry for all the FIXMEs here, but this will need further refactoring
        clean_data: list[FileMetaData] = []
        for d in data:
            if d.project_id not in prj_names_mapping:
                continue
            d.project_name = prj_names_mapping[d.project_id]
            if d.node_id in prj_names_mapping:
                d.node_name = prj_names_mapping[d.node_id]
            if d.node_name and d.project_name:
                clean_data.append(d)

            data = clean_data
        return data

    async def get_file(self, user_id: UserID, file_id: StorageFileID) -> FileMetaData:
        async with self.engine.acquire() as conn, conn.begin():
            can: AccessRights | None = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if can.read:
                fmd: FileMetaDataAtDB = await db_file_meta_data.get(
                    conn, parse_obj_as(SimcoreS3FileID, file_id)
                )
                if is_file_entry_valid(fmd):
                    return convert_db_to_model(fmd)
                fmd = await self._update_database_from_storage(conn, fmd)
                return convert_db_to_model(fmd)

            logger.debug("User %s cannot read file %s", user_id, file_id)
            raise FileAccessRightError(access_right="read", file_id=file_id)

    async def create_file_upload_links(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        link_type: LinkType,
        file_size_bytes: ByteSize,
        *,
        is_directory: bool,
    ) -> UploadLinks:
        async with self.engine.acquire() as conn, conn.begin() as transaction:
            can: AccessRights | None = await get_file_access_rights(
                conn, user_id, file_id
            )
            if not can.write:
                raise FileAccessRightError(access_right="write", file_id=file_id)

            # NOTE: if this gets called successively with the same file_id, and
            # there was a multipart upload in progress beforehand, it MUST be
            # cancelled to prevent unwanted costs in AWS
            await self._clean_pending_upload(
                conn, parse_obj_as(SimcoreS3FileID, file_id)
            )

            # initiate the file meta data table
            fmd = await self._create_fmd_for_upload(
                conn,
                user_id,
                file_id,
                upload_id=S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
                if (
                    get_s3_client(self.app).is_multipart(file_size_bytes)
                    or link_type == LinkType.S3
                )
                else None,
                is_directory=is_directory,
            )
            # NOTE: ensure the database is updated so cleaner does not pickup newly created uploads
            await transaction.commit()

            if link_type == LinkType.PRESIGNED and get_s3_client(self.app).is_multipart(
                file_size_bytes
            ):
                # create multipart links
                assert file_size_bytes  # nosec
                multipart_presigned_links = await get_s3_client(
                    self.app
                ).create_multipart_upload_links(
                    fmd.bucket_name,
                    fmd.file_id,
                    file_size_bytes,
                    expiration_secs=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
                )
                # update the database so we keep the upload id
                fmd.upload_id = multipart_presigned_links.upload_id
                await db_file_meta_data.upsert(conn, fmd)
                return UploadLinks(
                    multipart_presigned_links.urls,
                    multipart_presigned_links.chunk_size,
                )
            if link_type == LinkType.PRESIGNED:
                # create single presigned link
                single_presigned_link = await get_s3_client(
                    self.app
                ).create_single_presigned_upload_link(
                    self.simcore_bucket_name,
                    fmd.file_id,
                    expiration_secs=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
                )
                return UploadLinks(
                    [single_presigned_link],
                    file_size_bytes or MAX_LINK_CHUNK_BYTE_SIZE[link_type],
                )

        # user wants just the s3 link
        s3_link = get_s3_client(self.app).compute_s3_url(
            self.simcore_bucket_name, parse_obj_as(SimcoreS3FileID, file_id)
        )
        return UploadLinks(
            [s3_link], file_size_bytes or MAX_LINK_CHUNK_BYTE_SIZE[link_type]
        )

    async def abort_file_upload(
        self,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> None:
        async with self.engine.acquire() as conn, conn.begin():
            can: AccessRights | None = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.delete or not can.write:
                raise FileAccessRightError(access_right="write/delete", file_id=file_id)

            fmd: FileMetaDataAtDB = await db_file_meta_data.get(
                conn, parse_obj_as(SimcoreS3FileID, file_id)
            )
            if is_valid_managed_multipart_upload(fmd.upload_id):
                assert fmd.upload_id  # nosec
                await get_s3_client(self.app).abort_multipart_upload(
                    bucket=fmd.bucket_name,
                    file_id=fmd.file_id,
                    upload_id=fmd.upload_id,
                )

            try:
                # try to revert to what we had in storage if any
                await self._update_database_from_storage(conn, fmd)
            except S3KeyNotFoundError:
                # the file does not exist, so we delete the entry in the db
                async with self.engine.acquire() as conn:
                    await db_file_meta_data.delete(conn, [fmd.file_id])

    async def complete_file_upload(
        self,
        file_id: StorageFileID,
        user_id: UserID,
        uploaded_parts: list[UploadedPart],
    ) -> FileMetaData:
        async with self.engine.acquire() as conn:
            can: AccessRights | None = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.write:
                raise FileAccessRightError(access_right="write", file_id=file_id)
            fmd = await db_file_meta_data.get(
                conn, parse_obj_as(SimcoreS3FileID, file_id)
            )

        if is_valid_managed_multipart_upload(fmd.upload_id):
            # NOTE: Processing of a Complete Multipart Upload request
            # could take several minutes to complete. After Amazon S3
            # begins processing the request, it sends an HTTP response
            # header that specifies a 200 OK response. While processing
            # is in progress, Amazon S3 periodically sends white space
            # characters to keep the connection from timing out. Because
            # a request could fail after the initial 200 OK response
            # has been sent, it is important that you check the response
            # body to determine whether the request succeeded.
            assert fmd.upload_id  # nosec
            await get_s3_client(self.app).complete_multipart_upload(
                bucket=self.simcore_bucket_name,
                file_id=fmd.file_id,
                upload_id=fmd.upload_id,
                uploaded_parts=uploaded_parts,
            )
        async with self.engine.acquire() as conn:
            fmd = await self._update_database_from_storage(conn, fmd)
            assert fmd  # nosec
            return convert_db_to_model(fmd)

    async def create_file_download_link(
        self, user_id: UserID, file_id: StorageFileID, link_type: LinkType
    ) -> AnyUrl:
        """
        Cases:
        1. the file_id maps 1:1 to `file_meta_data` (e.g. it is not a file inside a directory)
        2. the file_id represents a file inside a directory (its root path maps 1:1 to a `file_meta_data` defined as a directory)

        3. Raises FileNotFoundError if the file does not exist
        4. Raises FileAccessRightError if the user does not have access to the file
        """
        async with self.engine.acquire() as conn:
            directory_file_id: SimcoreS3FileID | None = await get_directory_file_id(
                conn, cast(SimcoreS3FileID, file_id)
            )
            return (
                await self._get_link_for_directory_fmd(
                    conn, user_id, directory_file_id, file_id, link_type
                )
                if directory_file_id
                else await self._get_link_for_file_fmd(
                    conn, user_id, file_id, link_type
                )
            )

    async def __get_link(
        self, s3_file_id: SimcoreS3FileID, link_type: LinkType
    ) -> AnyUrl:
        link: AnyUrl = parse_obj_as(
            AnyUrl,
            f"s3://{self.simcore_bucket_name}/{urllib.parse.quote(s3_file_id)}",
        )
        if link_type == LinkType.PRESIGNED:
            link = await get_s3_client(self.app).create_single_presigned_download_link(
                self.simcore_bucket_name,
                s3_file_id,
                self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
            )

        return link

    async def _get_link_for_file_fmd(
        self,
        conn: SAConnection,
        user_id: UserID,
        file_id: StorageFileID,
        link_type: LinkType,
    ) -> AnyUrl:
        # 1. the file_id maps 1:1 to `file_meta_data`
        await ensure_read_access_rights(conn, user_id, file_id)

        fmd = await db_file_meta_data.get(conn, parse_obj_as(SimcoreS3FileID, file_id))
        if not is_file_entry_valid(fmd):
            # try lazy update
            fmd = await self._update_database_from_storage(conn, fmd)

        return await self.__get_link(fmd.object_name, link_type)

    async def _get_link_for_directory_fmd(
        self,
        conn: SAConnection,
        user_id: UserID,
        directory_file_id: SimcoreS3FileID,
        file_id: StorageFileID,
        link_type: LinkType,
    ) -> AnyUrl:
        # 2. the file_id represents a file inside a directory
        await ensure_read_access_rights(conn, user_id, directory_file_id)
        if not await get_s3_client(self.app).file_exists(
            self.simcore_bucket_name, s3_object=f"{file_id}"
        ):
            raise S3KeyNotFoundError(key=file_id, bucket=self.simcore_bucket_name)
        return await self.__get_link(parse_obj_as(SimcoreS3FileID, file_id), link_type)

    async def delete_file(self, user_id: UserID, file_id: StorageFileID):
        async with self.engine.acquire() as conn, conn.begin():
            can: AccessRights | None = await get_file_access_rights(
                conn, user_id, file_id
            )
            if not can.delete:
                raise FileAccessRightError(access_right="delete", file_id=file_id)

            with suppress(FileMetaDataNotFoundError):
                file: FileMetaDataAtDB = await db_file_meta_data.get(
                    conn, parse_obj_as(SimcoreS3FileID, file_id)
                )
                # NOTE: since this lists the files before deleting them
                # it can be used to filter for just a single file and also
                # to delete it
                await get_s3_client(self.app).delete_files_in_path(
                    file.bucket_name,
                    prefix=(
                        ensure_ends_with(file.file_id, "/")
                        if file.is_directory
                        else file.file_id
                    ),
                )
                await db_file_meta_data.delete(conn, [file.file_id])

    async def delete_project_simcore_s3(
        self, user_id: UserID, project_id: ProjectID, node_id: NodeID | None = None
    ) -> None:
        async with self.engine.acquire() as conn, conn.begin():
            can: AccessRights | None = await get_project_access_rights(
                conn, user_id, project_id
            )
            if not can.delete:
                raise ProjectAccessRightError(
                    access_right="delete", project_id=project_id
                )

            # we can do it this way, since we are in a transaction, it will rollback in case of error
            if not node_id:
                await db_file_meta_data.delete_all_from_project(conn, project_id)
            else:
                await db_file_meta_data.delete_all_from_node(conn, node_id)
            await get_s3_client(self.app).delete_files_in_project_node(
                self.simcore_bucket_name, project_id, node_id
            )

    async def deep_copy_project_simcore_s3(
        self,
        user_id: UserID,
        src_project: dict[str, Any],
        dst_project: dict[str, Any],
        node_mapping: dict[NodeID, NodeID],
        task_progress: TaskProgress | None = None,
    ) -> None:
        src_project_uuid: ProjectID = ProjectID(src_project["uuid"])
        dst_project_uuid: ProjectID = ProjectID(dst_project["uuid"])
        # Step 1: check access rights (read of src and write of dst)
        update_task_progress(task_progress, "Checking study access rights...")
        async with self.engine.acquire() as conn:
            for prj_uuid in [src_project_uuid, dst_project_uuid]:
                if not await db_projects.project_exists(conn, prj_uuid):
                    raise ProjectNotFoundError(project_id=prj_uuid)
            source_access_rights = await get_project_access_rights(
                conn, user_id, project_id=src_project_uuid
            )
            dest_access_rights = await get_project_access_rights(
                conn, user_id, project_id=dst_project_uuid
            )
        if not source_access_rights.read:
            raise ProjectAccessRightError(
                access_right="read", project_id=src_project_uuid
            )
        if not dest_access_rights.write:
            raise ProjectAccessRightError(
                access_right="write", project_id=dst_project_uuid
            )

        # Step 2: start copying by listing what to copy
        update_task_progress(
            task_progress, f"Collecting files of '{src_project['name']}'..."
        )
        async with self.engine.acquire() as conn:
            src_project_files: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_fmds(conn, project_ids=[src_project_uuid])
        project_file_sizes: list[ByteSize] = await logged_gather(
            *[self._get_size(fmd) for fmd in src_project_files],
            max_concurrency=_MAX_PARALLEL_S3_CALLS,
        )
        src_project_total_data_size: ByteSize = parse_obj_as(
            ByteSize, sum(project_file_sizes)
        )
        # Step 3.1: copy: files referenced from file_metadata
        copy_tasks: deque[Awaitable] = deque()
        s3_transfered_data_cb = S3TransferDataCB(
            task_progress,
            src_project_total_data_size,
            task_progress_message_prefix=f"Copying {len(src_project_files)} files to '{dst_project['name']}'",
        )
        for src_fmd in src_project_files:
            if not src_fmd.node_id or (src_fmd.location_id != self.location_id):
                msg = (
                    "This is not foreseen, stem from old decisions, and needs to "
                    f"be implemented if needed. Faulty metadata: {src_fmd=}"
                )
                raise NotImplementedError(msg)

            if new_node_id := node_mapping.get(src_fmd.node_id):
                copy_tasks.append(
                    self._copy_path_s3_s3(
                        user_id,
                        src_fmd,
                        SimcoreS3FileID(
                            f"{dst_project_uuid}/{new_node_id}/{src_fmd.object_name.split('/', maxsplit=2)[-1]}"
                        ),
                        bytes_transfered_cb=s3_transfered_data_cb.copy_transfer_cb,
                    )
                )
        # Step 3.2: copy files referenced from file-picker from DAT-CORE
        for node_id, node in dst_project.get("workbench", {}).items():
            copy_tasks.extend(
                [
                    self._copy_file_datcore_s3(
                        user_id=user_id,
                        source_uuid=output["path"],
                        dest_project_id=dst_project_uuid,
                        dest_node_id=NodeID(node_id),
                        file_storage_link=output,
                        bytes_transfered_cb=s3_transfered_data_cb.copy_transfer_cb,
                    )
                    for output in node.get("outputs", {}).values()
                    if isinstance(output, dict)
                    and (int(output.get("store", self.location_id)) == DATCORE_ID)
                ]
            )
        await logged_gather(*copy_tasks, max_concurrency=MAX_CONCURRENT_S3_TASKS)
        # ensure the full size is reported
        s3_transfered_data_cb.finalize_transfer()

    async def _get_size(self, fmd: FileMetaDataAtDB) -> ByteSize:
        if not fmd.is_directory:
            return fmd.file_size

        # in case of directory list files and return size
        total_size: int = 0
        async for s3_objects in get_s3_client(self.app).list_all_objects_gen(
            self.simcore_bucket_name,
            prefix=f"{fmd.object_name}",
            max_yield_result_size=_MAX_ELEMENTS_TO_LIST,
        ):
            total_size += sum(x.get("Size", 0) for x in s3_objects)

        return parse_obj_as(ByteSize, total_size)

    async def search_files_starting_with(
        self, user_id: UserID, prefix: str
    ) -> list[FileMetaData]:
        # NOTE: this entrypoint is solely used by api-server. It is the exact
        # same as list_files but does not rename the found files with project
        # name/node name which filters out this files
        # TODO: unify, or use a query parameter?
        async with self.engine.acquire() as conn:
            can_read_projects_ids = await get_readable_project_ids(conn, user_id)
            file_metadatas: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_filter_with_partial_file_id(
                conn,
                user_id=user_id,
                project_ids=can_read_projects_ids,
                file_id_prefix=prefix,
                partial_file_id=None,
                only_files=True,
            )
            resolved_fmds = []
            for fmd in file_metadatas:
                if is_file_entry_valid(fmd):
                    resolved_fmds.append(convert_db_to_model(fmd))
                    continue
                with suppress(S3KeyNotFoundError):
                    updated_fmd = await self._update_database_from_storage(conn, fmd)
                    resolved_fmds.append(convert_db_to_model(updated_fmd))
            return resolved_fmds

    async def create_soft_link(
        self, user_id: int, target_file_id: StorageFileID, link_file_id: StorageFileID
    ) -> FileMetaData:
        async with self.engine.acquire() as conn:
            if await db_file_meta_data.exists(
                conn, parse_obj_as(SimcoreS3FileID, link_file_id)
            ):
                raise LinkAlreadyExistsError(file_id=link_file_id)
        # validate target_uuid
        target = await self.get_file(user_id, target_file_id)
        # duplicate target and change the following columns:
        target.file_uuid = link_file_id
        target.file_id = link_file_id  # NOTE: api-server relies on this id
        target.is_soft_link = True

        async with self.engine.acquire() as conn:
            return convert_db_to_model(await db_file_meta_data.insert(conn, target))

    async def synchronise_meta_data_table(
        self, *, dry_run: bool
    ) -> list[StorageFileID]:
        file_ids_to_remove = []
        async with self.engine.acquire() as conn:
            logger.warning(
                "Total number of entries to check %d",
                await db_file_meta_data.total(conn),
            )
            # iterate over all entries to check if there is a file in the S3 backend
            async for fmd in db_file_meta_data.list_valid_uploads(conn):
                if not await get_s3_client(self.app).file_exists(
                    self.simcore_bucket_name, s3_object=fmd.object_name
                ):
                    # this file does not exist in S3
                    file_ids_to_remove.append(fmd.file_id)

            if not dry_run:
                await db_file_meta_data.delete(conn, file_ids_to_remove)

            logger.info(
                "%s %d entries ",
                "Would delete" if dry_run else "Deleted",
                len(file_ids_to_remove),
            )

        return file_ids_to_remove

    async def _clean_pending_upload(self, conn: SAConnection, file_id: SimcoreS3FileID):
        with suppress(FileMetaDataNotFoundError):
            fmd = await db_file_meta_data.get(conn, file_id)
            if is_valid_managed_multipart_upload(fmd.upload_id):
                assert fmd.upload_id  # nosec
                await get_s3_client(self.app).abort_multipart_upload(
                    bucket=self.simcore_bucket_name,
                    file_id=file_id,
                    upload_id=fmd.upload_id,
                )

    async def _clean_expired_uploads(self):
        """this method will check for all incomplete updates by checking
        the upload_expires_at entry in file_meta_data table.
        1. will try to update the entry from S3 backend if exists
        2. will delete the entry if nothing exists in S3 backend.
        """
        now = datetime.datetime.utcnow()
        async with self.engine.acquire() as conn:
            list_of_expired_uploads = await db_file_meta_data.list_fmds(
                conn, expired_after=now
            )
        logger.debug(
            "found following pending uploads: [%s]",
            [fmd.file_id for fmd in list_of_expired_uploads],
        )
        if not list_of_expired_uploads:
            return

        # try first to upload these from S3 (conservative)
        updated_fmds = await logged_gather(
            *(
                self._update_database_from_storage_no_connection(fmd)
                for fmd in list_of_expired_uploads
            ),
            reraise=False,
            log=logger,
            max_concurrency=MAX_CONCURRENT_DB_TASKS,
        )
        list_of_fmds_to_delete = [
            expired_fmd
            for expired_fmd, updated_fmd in zip(
                list_of_expired_uploads, updated_fmds, strict=True
            )
            if not isinstance(updated_fmd, FileMetaDataAtDB)
        ]
        if list_of_fmds_to_delete:
            # delete the remaining ones
            logger.debug(
                "following unfinished/incomplete uploads will now be deleted : [%s]",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )
            await logged_gather(
                *(
                    self.delete_file(fmd.user_id, fmd.file_id)
                    for fmd in list_of_fmds_to_delete
                    if fmd.user_id is not None
                ),
                log=logger,
                max_concurrency=MAX_CONCURRENT_DB_TASKS,
            )
            logger.warning(
                "pending/incomplete uploads of [%s] removed",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )

    async def _clean_dangling_multipart_uploads(self):
        """this method removes any dangling multipart upload that
        was initiated on S3 backend if it does not exist in file_meta_data
        table.
        Use-cases:
            - presigned multipart upload: a multipart upload is created after the entry in the table (
                if the expiry date is still in the future we do not remove the upload
            )
            - S3 external or internal potentially multipart upload (using S3 direct access we do not know
            if they create multipart uploads and have no control over it, the only thing we know is the upload
            expiry date)
            --> we only remove dangling upload IDs which expiry date is in the past or that have no upload in process
            or no entry at all in the database

        """
        current_multipart_uploads: list[
            tuple[UploadID, SimcoreS3FileID]
        ] = await get_s3_client(self.app).list_ongoing_multipart_uploads(
            self.simcore_bucket_name
        )
        if not current_multipart_uploads:
            return

        # there are some multipart uploads, checking if
        # there is a counterpart in file_meta_data
        # NOTE: S3 url encode file uuid with specific characters
        async with self.engine.acquire() as conn:
            # files have a 1 to 1 entry in the file_meta_data table
            file_ids: list[SimcoreS3FileID] = [
                SimcoreS3FileID(urllib.parse.unquote(f))
                for _, f in current_multipart_uploads
            ]
            # if a file is part of directory, check if this directory is present in
            # the file_meta_data table; extracting the SimcoreS3DirectoryID from
            # the file path to find it's equivalent
            directory_and_file_ids: list[SimcoreS3FileID] = file_ids + [
                SimcoreS3FileID(get_simcore_directory(file_id)) for file_id in file_ids
            ]

            list_of_known_metadata_entries: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_fmds(
                conn, file_ids=list(set(directory_and_file_ids))
            )
        # known uploads do have an expiry date (regardless of upload ID that we do not always know)
        list_of_known_uploads = [
            fmd for fmd in list_of_known_metadata_entries if fmd.upload_expires_at
        ]

        # To compile the list of valid uploads, check that the s3_object is
        # part of the known uploads.
        # The known uploads is composed of entries for files or for directories.
        # checking if the s3_object is part of either one of those
        list_of_valid_upload_ids: list[str] = []
        known_directory_names: set[str] = {
            x.object_name for x in list_of_known_uploads if x.is_directory is True
        }
        known_file_names: set[str] = {
            x.object_name for x in list_of_known_uploads if x.is_directory is False
        }
        for upload_id, s3_object_name in current_multipart_uploads:
            file_id = SimcoreS3FileID(urllib.parse.unquote(s3_object_name))
            if (
                file_id in known_file_names
                or get_simcore_directory(file_id) in known_directory_names
            ):
                list_of_valid_upload_ids.append(upload_id)

        list_of_invalid_uploads = [
            (
                upload_id,
                file_id,
            )
            for upload_id, file_id in current_multipart_uploads
            if upload_id not in list_of_valid_upload_ids
        ]
        logger.debug(
            "the following %s was found and will now be aborted",
            f"{list_of_invalid_uploads=}",
        )
        await logged_gather(
            *(
                get_s3_client(self.app).abort_multipart_upload(
                    self.simcore_bucket_name, file_id, upload_id
                )
                for upload_id, file_id in list_of_invalid_uploads
            ),
            max_concurrency=MAX_CONCURRENT_S3_TASKS,
        )
        logger.warning(
            "Dangling multipart uploads '%s', were aborted. "
            "TIP: There were multipart uploads active on S3 with no counter-part in the file_meta_data database. "
            "This might indicate that something went wrong in how storage handles multipart uploads!!",
            f"{list_of_invalid_uploads}",
        )

    async def clean_expired_uploads(self) -> None:
        await self._clean_expired_uploads()
        await self._clean_dangling_multipart_uploads()

    async def _update_database_from_storage(
        self, conn: SAConnection, fmd: FileMetaDataAtDB
    ) -> FileMetaDataAtDB:
        s3_metadata: S3MetaData | None = None
        if not fmd.is_directory:
            s3_metadata = await get_s3_client(self.app).get_file_metadata(
                fmd.bucket_name, fmd.object_name
            )

        fmd = await db_file_meta_data.get(conn, fmd.file_id)
        if not fmd.is_directory and s3_metadata:
            fmd.file_size = parse_obj_as(ByteSize, s3_metadata.size)
            fmd.last_modified = s3_metadata.last_modified
            fmd.entity_tag = s3_metadata.e_tag
        fmd.upload_expires_at = None
        fmd.upload_id = None
        updated_fmd: FileMetaDataAtDB = await db_file_meta_data.upsert(
            conn, convert_db_to_model(fmd)
        )
        return updated_fmd

    async def _update_database_from_storage_no_connection(
        self, fmd: FileMetaDataAtDB
    ) -> FileMetaDataAtDB:
        async with self.engine.acquire() as conn:
            updated_fmd: FileMetaDataAtDB = await self._update_database_from_storage(
                conn, fmd
            )
        return updated_fmd

    async def _copy_file_datcore_s3(
        self,
        user_id: UserID,
        source_uuid: str,
        dest_project_id: ProjectID,
        dest_node_id: NodeID,
        file_storage_link: dict[str, Any],
        bytes_transfered_cb: Callable[[int], None],
    ) -> FileMetaData:
        session = get_client_session(self.app)
        # 2 steps: Get download link for local copy, then upload to S3
        # TODO: This should be a redirect stream!
        api_token, api_secret = await db_tokens.get_api_token_and_secret(
            self.app, user_id
        )
        dc_link = await datcore_adapter.get_file_download_presigned_link(
            self.app, api_token, api_secret, source_uuid
        )
        assert dc_link.path  # nosec
        filename = Path(dc_link.path).name
        dst_file_id = SimcoreS3FileID(f"{dest_project_id}/{dest_node_id}/{filename}")
        logger.debug("copying %s to %s", f"{source_uuid=}", f"{dst_file_id=}")

        with tempfile.TemporaryDirectory() as tmpdir:
            local_file_path = Path(tmpdir) / filename
            # Downloads DATCore -> local
            await download_to_file_or_raise(session, dc_link, local_file_path)

            # copying will happen using aioboto3, therefore multipart might happen
            async with self.engine.acquire() as conn, conn.begin() as transaction:
                new_fmd = await self._create_fmd_for_upload(
                    conn,
                    user_id,
                    dst_file_id,
                    upload_id=S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
                    is_directory=False,
                )
                # NOTE: ensure the database is updated so cleaner does not pickup newly created uploads
                await transaction.commit()
                # Uploads local -> S3
                await get_s3_client(self.app).upload_file(
                    self.simcore_bucket_name,
                    local_file_path,
                    dst_file_id,
                    bytes_transfered_cb,
                )
                updated_fmd = await self._update_database_from_storage(conn, new_fmd)
            file_storage_link["store"] = self.location_id
            file_storage_link["path"] = new_fmd.file_id

            logger.info("copied %s to %s", f"{source_uuid=}", f"{updated_fmd=}")

        return convert_db_to_model(updated_fmd)

    async def _copy_path_s3_s3(
        self,
        user_id: UserID,
        src_fmd: FileMetaDataAtDB,
        dst_file_id: SimcoreS3FileID,
        bytes_transfered_cb: Callable[[int], None],
    ) -> FileMetaData:
        logger.debug("copying %s to %s", f"{src_fmd=}", f"{dst_file_id=}")
        # copying will happen using aioboto3, therefore multipart might happen
        # NOTE: connection must be released to ensure database update
        async with self.engine.acquire() as conn, conn.begin() as transaction:
            new_fmd = await self._create_fmd_for_upload(
                conn,
                user_id,
                dst_file_id,
                upload_id=S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
                is_directory=src_fmd.is_directory,
            )
            # NOTE: ensure the database is updated so cleaner does not pickup newly created uploads
            await transaction.commit()

            s3_client: StorageS3Client = get_s3_client(self.app)

            if src_fmd.is_directory:
                async for s3_objects in s3_client.list_all_objects_gen(
                    self.simcore_bucket_name,
                    prefix=src_fmd.object_name,
                    max_yield_result_size=_MAX_ELEMENTS_TO_LIST,
                ):
                    s3_objects_src_to_new: dict[str, str] = {
                        x["Key"]: x["Key"].replace(
                            f"{src_fmd.object_name}", f"{new_fmd.object_name}"
                        )
                        for x in s3_objects
                    }

                    await logged_gather(
                        *[
                            s3_client.copy_file(
                                self.simcore_bucket_name,
                                cast(SimcoreS3FileID, src),
                                cast(SimcoreS3FileID, new),
                                bytes_transfered_cb=bytes_transfered_cb,
                            )
                            for src, new in s3_objects_src_to_new.items()
                        ],
                        max_concurrency=_MAX_PARALLEL_S3_CALLS,
                    )
            else:
                await s3_client.copy_file(
                    self.simcore_bucket_name,
                    src_fmd.object_name,
                    new_fmd.object_name,
                    bytes_transfered_cb=bytes_transfered_cb,
                )

            updated_fmd = await self._update_database_from_storage(conn, new_fmd)
        logger.info("copied %s to %s", f"{src_fmd=}", f"{updated_fmd=}")
        return convert_db_to_model(updated_fmd)

    async def _create_fmd_for_upload(
        self,
        conn: SAConnection,
        user_id: UserID,
        file_id: StorageFileID,
        upload_id: UploadID | None,
        *,
        is_directory: bool,
    ) -> FileMetaDataAtDB:
        now = datetime.datetime.utcnow()
        upload_expiration_date = now + datetime.timedelta(
            seconds=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS
        )
        fmd = FileMetaData.from_simcore_node(
            user_id=user_id,
            file_id=parse_obj_as(SimcoreS3FileID, file_id),
            bucket=self.simcore_bucket_name,
            location_id=self.location_id,
            location_name=self.location_name,
            upload_expires_at=upload_expiration_date,
            upload_id=upload_id,
            is_directory=is_directory,
        )
        return await db_file_meta_data.upsert(conn, fmd)


def create_simcore_s3_data_manager(app: web.Application) -> SimcoreS3DataManager:
    cfg: Settings = app[APP_CONFIG_KEY]
    assert cfg.STORAGE_S3  # nosec
    return SimcoreS3DataManager(
        engine=app[APP_DB_ENGINE_KEY],
        simcore_bucket_name=parse_obj_as(S3BucketName, cfg.STORAGE_S3.S3_BUCKET_NAME),
        app=app,
        settings=cfg,
    )
