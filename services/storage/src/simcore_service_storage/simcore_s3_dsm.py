import contextlib
import datetime
import logging
import tempfile
import urllib.parse
from collections.abc import Coroutine
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import arrow
from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from aws_library.s3 import (
    CopiedBytesTransferredCallback,
    S3DirectoryMetaData,
    S3KeyNotFoundError,
    S3MetaData,
    UploadedBytesTransferredCallback,
)
from models_library.api_schemas_storage import (
    UNDEFINED_SIZE_TYPE,
    LinkType,
    S3BucketName,
    UploadedPart,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import (
    LocationID,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, NonNegativeInt, TypeAdapter
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.long_running_tasks.server import TaskProgress
from servicelib.logging_utils import log_context
from servicelib.utils import ensure_ends_with, limited_gather

from . import db_file_meta_data, db_projects, db_tokens
from .constants import (
    APP_AIOPG_ENGINE_KEY,
    APP_CONFIG_KEY,
    DATCORE_ID,
    EXPAND_DIR_MAX_ITEM_COUNT,
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
)
from .models import (
    DatasetMetaData,
    FileMetaData,
    FileMetaDataAtDB,
    UploadID,
    UploadLinks,
    UserOrProjectFilter,
)
from .s3 import get_s3_client
from .s3_utils import S3TransferDataCB, update_task_progress
from .settings import Settings
from .simcore_s3_dsm_utils import expand_directory, get_directory_file_id
from .utils import (
    convert_db_to_model,
    download_to_file_or_raise,
    is_file_entry_valid,
    is_valid_managed_multipart_upload,
)

_NO_CONCURRENCY: Final[int] = 1
_MAX_PARALLEL_S3_CALLS: Final[NonNegativeInt] = 10

_logger = logging.getLogger(__name__)


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
            project_id=None,
        )
        return data

    async def list_files(  # noqa C901
        self,
        user_id: UserID,
        *,
        expand_dirs: bool,
        uuid_filter: str,
        project_id: ProjectID | None,
    ) -> list[FileMetaData]:
        """
        expand_dirs `False`: returns one metadata entry for each directory
        expand_dirs `True`: returns all files in each directory (no directories will be included)
        project_id: If passed, only list files associated with that project_id
        uuid_filter: If passed, only list files whose 'object_name' match (ilike) the passed string

        NOTE: expand_dirs will be replaced by pagination in the future
        currently only {EXPAND_DIR_MAX_ITEM_COUNT} items will be returned
        The endpoint produces similar results to what it did previously
        """

        data: list[FileMetaData] = []
        accessible_projects_ids = []
        uid: UserID | None = None
        async with self.engine.acquire() as conn:
            if project_id is not None:
                project_access_rights = await get_project_access_rights(
                    conn=conn, user_id=user_id, project_id=project_id
                )
                if not project_access_rights.read:
                    raise ProjectAccessRightError(
                        access_right="read", project_id=project_id
                    )
                accessible_projects_ids = [project_id]
                uid = None
            else:
                accessible_projects_ids = await get_readable_project_ids(conn, user_id)
                uid = user_id
            file_and_directory_meta_data: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_filter_with_partial_file_id(
                conn,
                user_or_project_filter=UserOrProjectFilter(
                    user_id=uid, project_ids=accessible_projects_ids
                ),
                file_id_prefix=None,
                partial_file_id=uuid_filter,
                only_files=False,
                sha256_checksum=None,
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
                updated_fmd = await self._update_database_from_storage(metadata)
                data.append(convert_db_to_model(updated_fmd))

        # now parse the project to search for node/project names
        async with self.engine.acquire() as conn:
            prj_names_mapping: dict[ProjectID | NodeID, str] = {}
            async for proj_data in db_projects.list_valid_projects_in(
                conn, accessible_projects_ids
            ):
                prj_names_mapping |= {proj_data.uuid: proj_data.name} | {
                    NodeID(node_id): node_data.label
                    for node_id, node_data in proj_data.workbench.items()
                }

        # expand directories until the max number of files to return is reached
        directory_expands: list[Coroutine] = []
        for metadata in file_and_directory_meta_data:
            if (
                expand_dirs
                and metadata.is_directory
                and len(data) < EXPAND_DIR_MAX_ITEM_COUNT
            ):
                max_items_to_include = EXPAND_DIR_MAX_ITEM_COUNT - len(data)
                directory_expands.append(
                    expand_directory(
                        get_s3_client(self.app),
                        self.simcore_bucket_name,
                        metadata,
                        max_items_to_include,
                    )
                )
        for files_in_directory in await limited_gather(
            *directory_expands, limit=_MAX_PARALLEL_S3_CALLS
        ):
            data.extend(files_in_directory)

        # artifically fills ['project_name', 'node_name', 'file_id', 'raw_file_path', 'display_file_path']
        #   with information from the projects table!
        # NOTE: This part with the projects, should be done in the client code not here!
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
        async with self.engine.acquire() as conn:
            can: AccessRights = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.read:
                raise FileAccessRightError(access_right="read", file_id=file_id)

            fmd = await db_file_meta_data.get(
                conn, TypeAdapter(SimcoreS3FileID).validate_python(file_id)
            )
        if is_file_entry_valid(fmd):
            return convert_db_to_model(fmd)
        # get file from storage if available
        fmd = await self._update_database_from_storage(fmd)
        return convert_db_to_model(fmd)

    async def create_file_upload_links(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        link_type: LinkType,
        file_size_bytes: ByteSize,
        *,
        sha256_checksum: SHA256Str | None,
        is_directory: bool,
    ) -> UploadLinks:
        async with self.engine.acquire() as conn:
            can: AccessRights = await get_file_access_rights(conn, user_id, file_id)
            if not can.write:
                raise FileAccessRightError(access_right="write", file_id=file_id)

            # NOTE: if this gets called successively with the same file_id, and
            # there was a multipart upload in progress beforehand, it MUST be
            # cancelled to prevent unwanted costs in AWS
            await self._clean_pending_upload(
                conn, TypeAdapter(SimcoreS3FileID).validate_python(file_id)
            )

        if (
            not is_directory
        ):  # NOTE: Delete is not needed for directories that are synced via an external tool (rclone/aws s3 cli).
            # ensure file is deleted first in case it already exists
            # https://github.com/ITISFoundation/osparc-simcore/pull/5108
            await self.delete_file(
                user_id=user_id,
                file_id=file_id,
                # NOTE: bypassing check since the project access rights don't play well
                # with collaborators
                # SEE https://github.com/ITISFoundation/osparc-simcore/issues/5159
                enforce_access_rights=False,
            )
        async with self.engine.acquire() as conn:
            # initiate the file meta data table
            fmd = await self._create_fmd_for_upload(
                conn,
                user_id,
                file_id,
                upload_id=(
                    S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID
                    if (
                        get_s3_client(self.app).is_multipart(file_size_bytes)
                        or link_type == LinkType.S3
                    )
                    else None
                ),
                is_directory=is_directory,
                sha256_checksum=sha256_checksum,
            )

        if link_type == LinkType.PRESIGNED and get_s3_client(self.app).is_multipart(
            file_size_bytes
        ):
            # create multipart links
            assert file_size_bytes  # nosec
            multipart_presigned_links = await get_s3_client(
                self.app
            ).create_multipart_upload_links(
                bucket=fmd.bucket_name,
                object_key=fmd.file_id,
                file_size=file_size_bytes,
                expiration_secs=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
                sha256_checksum=fmd.sha256_checksum,
            )
            # update the database so we keep the upload id
            fmd.upload_id = multipart_presigned_links.upload_id
            async with self.engine.acquire() as conn:
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
                bucket=self.simcore_bucket_name,
                object_key=fmd.file_id,
                expiration_secs=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
            )
            return UploadLinks(
                [single_presigned_link],
                file_size_bytes or MAX_LINK_CHUNK_BYTE_SIZE[link_type],
            )

        # user wants just the s3 link
        s3_link = get_s3_client(self.app).compute_s3_url(
            bucket=self.simcore_bucket_name,
            object_key=TypeAdapter(SimcoreS3FileID).validate_python(file_id),
        )
        return UploadLinks(
            [s3_link], file_size_bytes or MAX_LINK_CHUNK_BYTE_SIZE[link_type]
        )

    async def abort_file_upload(
        self,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> None:
        async with self.engine.acquire() as conn:
            can: AccessRights = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.delete or not can.write:
                raise FileAccessRightError(access_right="write/delete", file_id=file_id)

            fmd: FileMetaDataAtDB = await db_file_meta_data.get(
                conn, TypeAdapter(SimcoreS3FileID).validate_python(file_id)
            )
        if is_valid_managed_multipart_upload(fmd.upload_id):
            assert fmd.upload_id  # nosec
            await get_s3_client(self.app).abort_multipart_upload(
                bucket=fmd.bucket_name,
                object_key=fmd.file_id,
                upload_id=fmd.upload_id,
            )
        # try to recover a file if it existed
        with contextlib.suppress(S3KeyNotFoundError):
            await get_s3_client(self.app).undelete_object(
                bucket=fmd.bucket_name, object_key=fmd.file_id
            )

        try:
            # try to revert to what we had in storage if any
            await self._update_database_from_storage(fmd)
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
            can: AccessRights = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.write:
                raise FileAccessRightError(access_right="write", file_id=file_id)
            fmd = await db_file_meta_data.get(
                conn, TypeAdapter(SimcoreS3FileID).validate_python(file_id)
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
                object_key=fmd.file_id,
                upload_id=fmd.upload_id,
                uploaded_parts=uploaded_parts,
            )
        fmd = await self._update_database_from_storage(fmd)
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
            await self.__ensure_read_access_rights(
                conn, user_id, directory_file_id if directory_file_id else file_id
            )
        if directory_file_id:
            if not await get_s3_client(self.app).object_exists(
                bucket=self.simcore_bucket_name, object_key=f"{file_id}"
            ):
                raise S3KeyNotFoundError(key=file_id, bucket=self.simcore_bucket_name)
            return await self.__get_link(
                TypeAdapter(SimcoreS3FileID).validate_python(file_id), link_type
            )
        # standard file link
        async with self.engine.acquire() as conn:
            fmd = await db_file_meta_data.get(
                conn, TypeAdapter(SimcoreS3FileID).validate_python(file_id)
            )
        if not is_file_entry_valid(fmd):
            # try lazy update
            fmd = await self._update_database_from_storage(fmd)
        return await self.__get_link(fmd.object_name, link_type)

    @staticmethod
    async def __ensure_read_access_rights(
        conn: SAConnection, user_id: UserID, storage_file_id: StorageFileID
    ) -> None:
        can: AccessRights = await get_file_access_rights(conn, user_id, storage_file_id)
        if not can.read:
            # NOTE: this is tricky. A user with read access can download and data!
            # If write permission would be required, then shared projects as views cannot
            # recover data in nodes (e.g. jupyter cannot pull work data)
            #
            raise FileAccessRightError(access_right="read", file_id=storage_file_id)

    async def __get_link(
        self, s3_file_id: SimcoreS3FileID, link_type: LinkType
    ) -> AnyUrl:
        link: AnyUrl = TypeAdapter(AnyUrl).validate_python(
            f"s3://{self.simcore_bucket_name}/{urllib.parse.quote(s3_file_id)}"
        )
        if link_type == LinkType.PRESIGNED:
            link = await get_s3_client(self.app).create_single_presigned_download_link(
                bucket=self.simcore_bucket_name,
                object_key=s3_file_id,
                expiration_secs=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
            )

        return link

    async def delete_file(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        *,
        enforce_access_rights: bool = True,
    ):
        #   _   _  ___ _____ _____
        #  | \ | |/ _ \_   _| ____|
        #  |  \| | | | || | |  _|
        #  | |\  | |_| || | | |___
        #  |_| \_|\___/ |_| |_____|
        # NOTE: (a very big one)
        # `enforce_access_rights` is set to False because permissions are based on "project access rights"
        # they should be based on data access rights (which is currently not present)
        # Only use this in those circumstances where a collaborator requires to delete a file (the current
        # permissions model will not allow him to do so, even though this is a legitimate action)
        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/5159
        async with self.engine.acquire() as conn:
            if enforce_access_rights:
                can: AccessRights = await get_file_access_rights(conn, user_id, file_id)
                if not can.delete:
                    raise FileAccessRightError(access_right="delete", file_id=file_id)

        with suppress(FileMetaDataNotFoundError):
            # NOTE: deleting might be slow, so better ensure we release the connection
            async with self.engine.acquire() as conn:
                file: FileMetaDataAtDB = await db_file_meta_data.get(
                    conn, TypeAdapter(SimcoreS3FileID).validate_python(file_id)
                )
            await get_s3_client(self.app).delete_objects_recursively(
                bucket=file.bucket_name,
                prefix=(
                    ensure_ends_with(file.file_id, "/")
                    if file.is_directory
                    else file.file_id
                ),
            )
            async with self.engine.acquire() as conn:
                await db_file_meta_data.delete(conn, [file.file_id])

    async def delete_project_simcore_s3(
        self, user_id: UserID, project_id: ProjectID, node_id: NodeID | None = None
    ) -> None:
        async with self.engine.acquire() as conn:
            can: AccessRights = await get_project_access_rights(
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

        await get_s3_client(self.app).delete_objects_recursively(
            bucket=self.simcore_bucket_name,
            prefix=ensure_ends_with(
                f"{project_id}/{node_id}" if node_id else f"{project_id}", "/"
            ),
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
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{src_project_uuid} -> {dst_project_uuid}: "
            "Step 1: check access rights (read of src and write of dst)",
        ):
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

        with log_context(
            _logger,
            logging.INFO,
            msg=f"{src_project_uuid} -> {dst_project_uuid}:"
            " Step 2: collect what to copy",
        ):
            update_task_progress(
                task_progress, f"Collecting files of '{src_project['name']}'..."
            )
            async with self.engine.acquire() as conn:
                src_project_files: list[
                    FileMetaDataAtDB
                ] = await db_file_meta_data.list_fmds(
                    conn, project_ids=[src_project_uuid]
                )

            with log_context(
                _logger,
                logging.INFO,
                f"{src_project_uuid} -> {dst_project_uuid}: get total file size for "
                f"{len(src_project_files)} files",
                log_duration=True,
            ):
                sizes_and_num_files: list[
                    tuple[ByteSize | UNDEFINED_SIZE_TYPE, int]
                ] = await limited_gather(
                    *[self._get_size_and_num_files(fmd) for fmd in src_project_files],
                    limit=_MAX_PARALLEL_S3_CALLS,
                )
            total_num_of_files = sum(n for _, n in sizes_and_num_files)
            src_project_total_data_size: ByteSize = TypeAdapter(
                ByteSize
            ).validate_python(sum(n for n, _ in sizes_and_num_files))
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{src_project_uuid} -> {dst_project_uuid}:"
            " Step 3.1: prepare copy tasks for files referenced from simcore",
        ):
            copy_tasks = []
            s3_transfered_data_cb = S3TransferDataCB(
                task_progress,
                src_project_total_data_size,
                task_progress_message_prefix=f"Copying {total_num_of_files} files to '{dst_project['name']}'",
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
                            src_fmd=src_fmd,
                            dst_file_id=TypeAdapter(SimcoreS3FileID).validate_python(
                                f"{dst_project_uuid}/{new_node_id}/{src_fmd.object_name.split('/', maxsplit=2)[-1]}"
                            ),
                            bytes_transfered_cb=s3_transfered_data_cb.copy_transfer_cb,
                        )
                    )
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{src_project_uuid} -> {dst_project_uuid}:"
            " Step 3.1: prepare copy tasks for files referenced from DAT-CORE",
        ):
            for node_id, node in dst_project.get("workbench", {}).items():
                copy_tasks.extend(
                    [
                        self._copy_file_datcore_s3(
                            user_id=user_id,
                            source_uuid=output["path"],
                            dest_project_id=dst_project_uuid,
                            dest_node_id=NodeID(node_id),
                            file_storage_link=output,
                            bytes_transfered_cb=s3_transfered_data_cb.upload_transfer_cb,
                        )
                        for output in node.get("outputs", {}).values()
                        if isinstance(output, dict)
                        and (int(output.get("store", self.location_id)) == DATCORE_ID)
                    ]
                )
        with log_context(
            _logger,
            logging.INFO,
            msg=f"{src_project_uuid} -> {dst_project_uuid}: Step 3.3: effective copying {len(copy_tasks)} files",
        ):
            await limited_gather(*copy_tasks, limit=MAX_CONCURRENT_S3_TASKS)

        # ensure the full size is reported
        s3_transfered_data_cb.finalize_transfer()

    async def _get_size_and_num_files(
        self, fmd: FileMetaDataAtDB
    ) -> tuple[ByteSize | UNDEFINED_SIZE_TYPE, int]:
        if not fmd.is_directory:
            return fmd.file_size, 1

        # in case of directory list files and return size
        total_size: int = 0
        total_num_s3_objects = 0
        async for s3_objects in get_s3_client(self.app).list_objects_paginated(
            bucket=self.simcore_bucket_name,
            prefix=(
                ensure_ends_with(f"{fmd.object_name}", "/")
                if fmd.is_directory
                else fmd.object_name
            ),
        ):
            total_size += sum(x.size for x in s3_objects)
            total_num_s3_objects += len(s3_objects)

        return TypeAdapter(ByteSize).validate_python(total_size), total_num_s3_objects

    async def search_owned_files(
        self,
        *,
        user_id: UserID,
        file_id_prefix: str | None,
        sha256_checksum: SHA256Str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[FileMetaData]:
        async with self.engine.acquire() as conn:
            file_metadatas: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_filter_with_partial_file_id(
                conn,
                user_or_project_filter=UserOrProjectFilter(
                    user_id=user_id, project_ids=[]
                ),
                file_id_prefix=file_id_prefix,
                partial_file_id=None,
                only_files=True,
                sha256_checksum=sha256_checksum,
                limit=limit,
                offset=offset,
            )
        resolved_fmds = []
        for fmd in file_metadatas:
            if is_file_entry_valid(fmd):
                resolved_fmds.append(convert_db_to_model(fmd))
                continue
            with suppress(S3KeyNotFoundError):
                updated_fmd = await self._update_database_from_storage(fmd)
                resolved_fmds.append(convert_db_to_model(updated_fmd))
        return resolved_fmds

    async def create_soft_link(
        self, user_id: int, target_file_id: StorageFileID, link_file_id: StorageFileID
    ) -> FileMetaData:
        async with self.engine.acquire() as conn:
            if await db_file_meta_data.exists(
                conn, TypeAdapter(SimcoreS3FileID).validate_python(link_file_id)
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

        async with self.engine.acquire() as conn:
            _logger.warning(
                "Total number of entries to check %d",
                await db_file_meta_data.total(conn),
            )
            # iterate over all entries to check if there is a file in the S3 backend
            file_ids_to_remove = [
                fmd.file_id
                async for fmd in db_file_meta_data.list_valid_uploads(conn)
                if not await get_s3_client(self.app).object_exists(
                    bucket=self.simcore_bucket_name, object_key=fmd.object_name
                )
            ]

            if not dry_run:
                await db_file_meta_data.delete(conn, file_ids_to_remove)

            _logger.info(
                "%s %d entries ",
                "Would delete" if dry_run else "Deleted",
                len(file_ids_to_remove),
            )

        return cast(list[StorageFileID], file_ids_to_remove)

    async def _clean_pending_upload(
        self, conn: SAConnection, file_id: SimcoreS3FileID
    ) -> None:
        with suppress(FileMetaDataNotFoundError):
            fmd = await db_file_meta_data.get(conn, file_id)
            if is_valid_managed_multipart_upload(fmd.upload_id):
                assert fmd.upload_id  # nosec
                await get_s3_client(self.app).abort_multipart_upload(
                    bucket=self.simcore_bucket_name,
                    object_key=file_id,
                    upload_id=fmd.upload_id,
                )

    async def _clean_expired_uploads(self) -> None:
        """this method will check for all incomplete updates by checking
        the upload_expires_at entry in file_meta_data table.
        1. will try to update the entry from S3 backend if exists
        2. will delete the entry if nothing exists in S3 backend.
        """
        now = arrow.utcnow().datetime
        async with self.engine.acquire() as conn:
            list_of_expired_uploads = await db_file_meta_data.list_fmds(
                conn, expired_after=now
            )

        if not list_of_expired_uploads:
            return
        _logger.debug(
            "found following expired uploads: [%s]",
            [fmd.file_id for fmd in list_of_expired_uploads],
        )

        # try first to upload these from S3, they might have finished and the client forgot to tell us (conservative)
        # NOTE: no concurrency here as we want to run low resources
        updated_fmds = await limited_gather(
            *(
                self._update_database_from_storage(fmd)
                for fmd in list_of_expired_uploads
            ),
            reraise=False,
            log=_logger,
            limit=_NO_CONCURRENCY,
        )

        list_of_fmds_to_delete = [
            expired_fmd
            for expired_fmd, updated_fmd in zip(
                list_of_expired_uploads, updated_fmds, strict=True
            )
            if not isinstance(updated_fmd, FileMetaDataAtDB)
        ]

        # try to revert the files if they exist
        async def _revert_file(fmd: FileMetaDataAtDB) -> FileMetaDataAtDB:
            if is_valid_managed_multipart_upload(fmd.upload_id):
                assert fmd.upload_id  # nosec
                await s3_client.abort_multipart_upload(
                    bucket=fmd.bucket_name,
                    object_key=fmd.file_id,
                    upload_id=fmd.upload_id,
                )
            await s3_client.undelete_object(
                bucket=fmd.bucket_name, object_key=fmd.file_id
            )
            return await self._update_database_from_storage(fmd)

        s3_client = get_s3_client(self.app)
        # NOTE: no concurrency here as we want to run low resources
        reverted_fmds = await limited_gather(
            *(_revert_file(fmd) for fmd in list_of_fmds_to_delete),
            reraise=False,
            log=_logger,
            limit=_NO_CONCURRENCY,
        )
        list_of_fmds_to_delete = [
            fmd
            for fmd, reverted_fmd in zip(
                list_of_fmds_to_delete, reverted_fmds, strict=True
            )
            if not isinstance(reverted_fmd, FileMetaDataAtDB)
        ]

        if list_of_fmds_to_delete:
            # delete the remaining ones
            _logger.debug(
                "following unfinished/incomplete uploads will now be deleted : [%s]",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )
            for fmd in list_of_fmds_to_delete:
                if fmd.user_id is not None:
                    await self.delete_file(fmd.user_id, fmd.file_id)

            _logger.warning(
                "pending/incomplete uploads of [%s] removed",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )

    async def clean_expired_uploads(self) -> None:
        await self._clean_expired_uploads()

    async def _update_fmd_from_other(
        self, conn: SAConnection, *, fmd: FileMetaDataAtDB, copy_from: FileMetaDataAtDB
    ) -> FileMetaDataAtDB:
        if not fmd.is_directory:
            s3_metadata = await get_s3_client(self.app).get_object_metadata(
                bucket=fmd.bucket_name, object_key=fmd.object_name
            )
            fmd.file_size = TypeAdapter(ByteSize).validate_python(s3_metadata.size)
            fmd.last_modified = s3_metadata.last_modified
            fmd.entity_tag = s3_metadata.e_tag
        else:
            # we spare calling get_directory_metadata as it is not needed now and is costly
            fmd.file_size = copy_from.file_size

        fmd.upload_expires_at = None
        fmd.upload_id = None
        updated_fmd: FileMetaDataAtDB = await db_file_meta_data.upsert(
            conn, convert_db_to_model(fmd)
        )
        return updated_fmd

    async def _get_s3_metadata(
        self, fmd: FileMetaDataAtDB
    ) -> S3MetaData | S3DirectoryMetaData:
        return (
            await get_s3_client(self.app).get_object_metadata(
                bucket=fmd.bucket_name, object_key=fmd.object_name
            )
            if not fmd.is_directory
            else await get_s3_client(self.app).get_directory_metadata(
                bucket=fmd.bucket_name, prefix=fmd.object_name
            )
        )

    async def _update_database_from_storage(
        self, fmd: FileMetaDataAtDB
    ) -> FileMetaDataAtDB:
        """
        Raises:
            S3KeyNotFoundError -- if the object key is not found in S3
        """
        s3_metadata = await self._get_s3_metadata(fmd)
        if not fmd.is_directory:
            assert isinstance(s3_metadata, S3MetaData)  # nosec
            fmd.file_size = TypeAdapter(ByteSize).validate_python(s3_metadata.size)
            fmd.last_modified = s3_metadata.last_modified
            fmd.entity_tag = s3_metadata.e_tag
        elif fmd.is_directory:
            assert isinstance(s3_metadata, S3DirectoryMetaData)  # nosec
            fmd.file_size = TypeAdapter(ByteSize).validate_python(s3_metadata.size)
        fmd.upload_expires_at = None
        fmd.upload_id = None
        async with self.engine.acquire() as conn:
            updated_fmd: FileMetaDataAtDB = await db_file_meta_data.upsert(
                conn, convert_db_to_model(fmd)
            )
        return updated_fmd

    async def _copy_file_datcore_s3(
        self,
        user_id: UserID,
        source_uuid: str,
        dest_project_id: ProjectID,
        dest_node_id: NodeID,
        file_storage_link: dict[str, Any],
        bytes_transfered_cb: UploadedBytesTransferredCallback,
    ) -> FileMetaData:
        session = get_client_session(self.app)
        # 2 steps: Get download link for local copy, then upload to S3
        api_token, api_secret = await db_tokens.get_api_token_and_secret(
            self.app, user_id
        )
        dc_link = await datcore_adapter.get_file_download_presigned_link(
            self.app, api_token, api_secret, source_uuid
        )
        assert dc_link.path  # nosec
        filename = Path(dc_link.path).name
        dst_file_id = TypeAdapter(SimcoreS3FileID).validate_python(
            f"{dest_project_id}/{dest_node_id}/{filename}"
        )
        _logger.debug("copying %s to %s", f"{source_uuid=}", f"{dst_file_id=}")

        with tempfile.TemporaryDirectory() as tmpdir:
            local_file_path = Path(tmpdir) / filename
            # Downloads DATCore -> local
            await download_to_file_or_raise(session, f"{dc_link}", local_file_path)

            # copying will happen using aioboto3, therefore multipart might happen
            async with self.engine.acquire() as conn:
                new_fmd = await self._create_fmd_for_upload(
                    conn,
                    user_id,
                    dst_file_id,
                    upload_id=S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
                    is_directory=False,
                    sha256_checksum=None,
                )
            # Uploads local -> S3
            await get_s3_client(self.app).upload_file(
                bucket=self.simcore_bucket_name,
                file=local_file_path,
                object_key=dst_file_id,
                bytes_transfered_cb=bytes_transfered_cb,
            )
            updated_fmd = await self._update_database_from_storage(fmd=new_fmd)
            file_storage_link["store"] = self.location_id
            file_storage_link["path"] = new_fmd.file_id

            _logger.info("copied %s to %s", f"{source_uuid=}", f"{updated_fmd=}")

        return convert_db_to_model(updated_fmd)

    async def _copy_path_s3_s3(
        self,
        user_id: UserID,
        *,
        src_fmd: FileMetaDataAtDB,
        dst_file_id: SimcoreS3FileID,
        bytes_transfered_cb: CopiedBytesTransferredCallback,
    ) -> FileMetaData:
        with log_context(
            _logger,
            logging.INFO,
            f"copying {src_fmd.file_id=} to {dst_file_id=}, {src_fmd.is_directory=}",
        ):
            # copying will happen using aioboto3, therefore multipart might happen
            # NOTE: connection must be released to ensure database update
            async with self.engine.acquire() as conn:
                new_fmd = await self._create_fmd_for_upload(
                    conn,
                    user_id,
                    dst_file_id,
                    upload_id=S3_UNDEFINED_OR_EXTERNAL_MULTIPART_ID,
                    is_directory=src_fmd.is_directory,
                    sha256_checksum=src_fmd.sha256_checksum,
                )

            s3_client = get_s3_client(self.app)

            if src_fmd.is_directory:
                await s3_client.copy_objects_recursively(
                    bucket=self.simcore_bucket_name,
                    src_prefix=src_fmd.object_name,
                    dst_prefix=new_fmd.object_name,
                    bytes_transfered_cb=bytes_transfered_cb,
                )
            else:
                await s3_client.copy_object(
                    bucket=self.simcore_bucket_name,
                    src_object_key=src_fmd.object_name,
                    dst_object_key=new_fmd.object_name,
                    bytes_transfered_cb=bytes_transfered_cb,
                )
            # we are done, let's update the copy with the src
            async with self.engine.acquire() as conn:
                updated_fmd = await self._update_fmd_from_other(
                    conn, fmd=new_fmd, copy_from=src_fmd
                )
            return convert_db_to_model(updated_fmd)

    async def _create_fmd_for_upload(
        self,
        conn: SAConnection,
        user_id: UserID,
        file_id: StorageFileID,
        upload_id: UploadID | None,
        *,
        is_directory: bool,
        sha256_checksum: SHA256Str | None,
    ) -> FileMetaDataAtDB:
        now = arrow.utcnow().datetime
        upload_expiration_date = now + datetime.timedelta(
            seconds=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS
        )
        fmd = FileMetaData.from_simcore_node(
            user_id=user_id,
            file_id=TypeAdapter(SimcoreS3FileID).validate_python(file_id),
            bucket=self.simcore_bucket_name,
            location_id=self.location_id,
            location_name=self.location_name,
            upload_expires_at=upload_expiration_date,
            upload_id=upload_id,
            is_directory=is_directory,
            sha256_checksum=sha256_checksum,
        )
        return await db_file_meta_data.upsert(conn, fmd)


def create_simcore_s3_data_manager(app: web.Application) -> SimcoreS3DataManager:
    cfg: Settings = app[APP_CONFIG_KEY]
    assert cfg.STORAGE_S3  # nosec
    return SimcoreS3DataManager(
        engine=app[APP_AIOPG_ENGINE_KEY],
        simcore_bucket_name=TypeAdapter(S3BucketName).validate_python(
            cfg.STORAGE_S3.S3_BUCKET_NAME
        ),
        app=app,
        settings=cfg,
    )
