import datetime
import logging
import tempfile
import urllib.parse
from collections import deque
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Optional, Union

from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from models_library.api_schemas_storage import LinkType, S3BucketName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import (
    LocationID,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from servicelib.utils import logged_gather
from simcore_service_storage import db_tokens
from simcore_service_storage.s3 import get_s3_client

from . import db_file_meta_data, db_projects
from .constants import (
    APP_CONFIG_KEY,
    APP_DB_ENGINE_KEY,
    DATCORE_ID,
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
    S3KeyNotFoundError,
)
from .models import DatasetMetaData, FileMetaData, FileMetaDataAtDB
from .settings import Settings
from .utils import convert_db_to_model, download_to_file_or_raise, is_file_entry_valid

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
        # always true for now
        return True

    async def list_datasets(self, user_id: UserID) -> list[DatasetMetaData]:
        async with self.engine.acquire() as conn:
            readable_projects_ids = await get_readable_project_ids(conn, user_id)
            # FIXME: this DOES NOT read from file-metadata table!!!
            return [
                DatasetMetaData(
                    dataset_id=prj_data.uuid,
                    display_name=prj_data.name,
                )
                async for prj_data in db_projects.list_projects(
                    conn, readable_projects_ids
                )
            ]

    async def list_files_in_dataset(
        self, user_id: UserID, dataset_id: str
    ) -> list[FileMetaData]:
        data: list[FileMetaData] = await self.list_files(
            user_id, uuid_filter=dataset_id + "/"
        )

        return data

    async def list_files(
        self, user_id: UserID, uuid_filter: str = ""
    ) -> list[FileMetaData]:
        data: deque[FileMetaData] = deque()
        accesible_projects_ids = []
        async with self.engine.acquire() as conn, conn.begin():
            accesible_projects_ids = await get_readable_project_ids(conn, user_id)
            file_metadatas: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_fmds_with_partial_file_id(
                conn,
                user_id=user_id,
                project_ids=accesible_projects_ids,
                file_id_prefix=None,
                partial_file_id=uuid_filter,
            )

            for fmd in file_metadatas:
                if is_file_entry_valid(fmd):
                    data.append(convert_db_to_model(fmd))
                    continue
                with suppress(S3KeyNotFoundError):
                    # 1. this was uploaded using the legacy file upload that relied on
                    # a background task checking the S3 backend unreliably, the file eventually
                    # will be uploaded and this will lazily update the database
                    # 2. this is still in upload and the file is missing and it will raise
                    updated_fmd = await self._update_database_from_storage(
                        conn, fmd.file_id, fmd.bucket_name, fmd.object_name
                    )
                    data.append(convert_db_to_model(updated_fmd))

            # now parse the project to search for node/project names
            # FIXME: this should be done in the client!
            prj_names_mapping: dict[Union[ProjectID, NodeID], str] = {}
            async for proj_data in db_projects.list_projects(
                conn, accesible_projects_ids
            ):
                prj_names_mapping = {proj_data.uuid: proj_data.name} | {
                    NodeID(node_id): node_data.label
                    for node_id, node_data in proj_data.workbench.items()
                }

        # FIXME: why is this done only here????
        # FIXME: artifically fills ['project_name', 'node_name', 'file_id', 'raw_file_path', 'display_file_path']
        #        with information from the projects table!
        # TODO: FIX THIS!!!
        # NOTE: sorry for all the FIXMEs here, but this will need further refactoring
        clean_data = deque()
        for d in data:
            if d.project_id not in prj_names_mapping:
                continue
            d.project_name = prj_names_mapping[d.project_id]
            if d.node_id in prj_names_mapping:
                d.node_name = prj_names_mapping[d.node_id]
            if d.node_name and d.project_name:
                clean_data.append(d)

            data = clean_data
        return list(data)

    async def get_file(self, user_id: UserID, file_id: StorageFileID) -> FileMetaData:
        async with self.engine.acquire() as conn, conn.begin():
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if can.read:
                file_metadata: FileMetaDataAtDB = await db_file_meta_data.get(
                    conn, parse_obj_as(SimcoreS3FileID, file_id)
                )
                if is_file_entry_valid(file_metadata):
                    return convert_db_to_model(file_metadata)
                file_metadata = await self._update_database_from_storage(
                    conn,
                    file_metadata.file_id,
                    file_metadata.bucket_name,
                    file_metadata.object_name,
                )
                return convert_db_to_model(file_metadata)

            logger.debug("User %s cannot read file %s", user_id, file_id)
            raise FileAccessRightError(file_id=file_id)

    async def create_file_upload_link(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        link_type: LinkType,
    ) -> AnyUrl:
        """returns: a presigned upload link"""
        async with self.engine.acquire() as conn, conn.begin():
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, user_id, file_id
            )
            if not can.write:
                raise web.HTTPForbidden(
                    reason=f"User {user_id} does not have enough access rights to upload file {file_id}"
                )

            # initiate the file meta data table
            upload_expiration_date = datetime.datetime.utcnow() + datetime.timedelta(
                seconds=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS
            )
            fmd = FileMetaData.from_simcore_node(
                user_id=user_id,
                file_id=parse_obj_as(SimcoreS3FileID, file_id),
                bucket=self.simcore_bucket_name,
                location_id=self.location_id,
                location_name=self.location_name,
                upload_expires_at=upload_expiration_date,
            )
            fmd = await db_file_meta_data.upsert_file_metadata_for_upload(conn, fmd)

            # return the appropriate links
            if link_type == LinkType.PRESIGNED:
                single_presigned_link = await get_s3_client(
                    self.app
                ).create_single_presigned_upload_link(
                    self.simcore_bucket_name,
                    fmd.file_id,
                    expiration_secs=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
                )
                return parse_obj_as(AnyUrl, f"{single_presigned_link}")

        # user wants just the s3 link
        s3_link = get_s3_client(self.app).compute_s3_url(
            self.simcore_bucket_name, parse_obj_as(SimcoreS3FileID, file_id)
        )
        return s3_link

    async def abort_file_upload(
        self,
        user_id: UserID,
        file_id: StorageFileID,
    ) -> None:
        """aborts a current upload and reverts to the last version if any.
        In case there are no previous version, removes the entry in the database
        """
        async with self.engine.acquire() as conn, conn.begin():
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.delete or not can.write:
                raise web.HTTPForbidden(
                    reason=f"User {user_id} does not have enough access rights to delete file {file_id}"
                )
            file: FileMetaDataAtDB = await db_file_meta_data.get(
                conn, parse_obj_as(SimcoreS3FileID, file_id)
            )

            try:
                # try to revert to what we had in storage if any
                await self._update_database_from_storage(
                    conn,
                    file.file_id,
                    file.bucket_name,
                    file.object_name,
                )
            except S3KeyNotFoundError:
                # the file does not exist, so we delete the entry in the db
                async with self.engine.acquire() as conn:
                    await db_file_meta_data.delete(conn, [file.file_id])

    async def create_file_download_link(
        self, user_id: UserID, file_id: StorageFileID, link_type: LinkType
    ) -> str:

        # access layer
        async with self.engine.acquire() as conn:
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, user_id, file_id
            )
            if not can.read:
                # NOTE: this is tricky. A user with read access can download and data!
                # If write permission would be required, then shared projects as views cannot
                # recover data in nodes (e.g. jupyter cannot pull work data)
                #
                raise web.HTTPForbidden(
                    reason=f"User {user_id} does not have enough rights to download file {file_id}"
                )

            fmd = await db_file_meta_data.get(
                conn, parse_obj_as(SimcoreS3FileID, file_id)
            )

        link = parse_obj_as(
            AnyUrl,
            f"s3://{self.simcore_bucket_name}/{urllib.parse.quote(fmd.object_name)}",
        )
        if link_type == LinkType.PRESIGNED:
            link = await get_s3_client(self.app).create_single_presigned_download_link(
                self.simcore_bucket_name,
                fmd.object_name,
                self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
            )

        return f"{link}"

    async def delete_file(self, user_id: UserID, file_id: StorageFileID):
        async with self.engine.acquire() as conn, conn.begin():
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, user_id, file_id
            )
            if not can.delete:
                raise web.HTTPForbidden(
                    reason=f"User {user_id} does not have enough access rights to delete file {file_id}"
                )
            with suppress(FileMetaDataNotFoundError):
                file: FileMetaDataAtDB = await db_file_meta_data.get(
                    conn, parse_obj_as(SimcoreS3FileID, file_id)
                )
                # deleting a non existing file simply works
                await get_s3_client(self.app).delete_file(
                    file.bucket_name, file.file_id
                )
                # now that we are done, remove it from the db
                await db_file_meta_data.delete(conn, [file.file_id])

    async def delete_project_simcore_s3(
        self, user_id: UserID, project_id: ProjectID, node_id: Optional[NodeID] = None
    ) -> None:

        """Deletes all files from a given node in a project in simcore.s3 and updated db accordingly.
        If node_id is not given, then all the project files db entries are deleted.
        """

        # FIXME: operation MUST be atomic. Mark for deletion and remove from db when deletion fully confirmed
        async with self.engine.acquire() as conn, conn.begin():
            # access layer
            can: Optional[AccessRights] = await get_project_access_rights(
                conn, user_id, project_id
            )
            if not can.delete:
                raise web.HTTPForbidden(
                    reason=f"User {user_id} does not have delete access for {project_id}"
                )

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
    ) -> None:
        src_project_uuid: ProjectID = ProjectID(src_project["uuid"])
        dst_project_uuid: ProjectID = ProjectID(dst_project["uuid"])
        # Step 1: check access rights (read of src and write of dst)
        async with self.engine.acquire() as conn:
            for prj_uuid in [src_project_uuid, dst_project_uuid]:
                if not await db_projects.project_exists(conn, prj_uuid):
                    raise web.HTTPNotFound(reason=f"Project '{prj_uuid}' not found")

            # access layer
            source_access_rights = await get_project_access_rights(
                conn, user_id, project_id=src_project_uuid
            )
            dest_access_rights = await get_project_access_rights(
                conn, user_id, project_id=dst_project_uuid
            )
        if not source_access_rights.read:
            raise web.HTTPForbidden(
                reason=f"User {user_id} does not have enough access rights to read from project '{src_project_uuid}'"
            )
        if not dest_access_rights.write:
            raise web.HTTPForbidden(
                reason=f"User {user_id} does not have enough access rights to write to project '{dst_project_uuid}'"
            )

        # Step 2: start copying by listing what to copy
        logger.debug(
            "Copying all items from  %s to %s",
            f"{self.simcore_bucket_name=}:{src_project_uuid=}",
            f"{self.simcore_bucket_name=}:{dst_project_uuid=}",
        )
        async with self.engine.acquire() as conn:
            src_project_files: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_fmds(conn, project_ids=[src_project_uuid])

        # Step 3.1: copy: files referenced from file_metadata
        copy_tasks: deque[Awaitable] = deque()
        for src_fmd in src_project_files:
            if not src_fmd.node_id or (src_fmd.location_id != SIMCORE_S3_ID):
                raise NotImplementedError(
                    "This is not foreseen, stem from old decisions"
                    f", and needs to be implemented if needed. Faulty metadata: {src_fmd=}"
                )

            if new_node_id := node_mapping.get(src_fmd.node_id):
                copy_tasks.append(
                    self._copy_file_s3_s3(
                        user_id,
                        src_fmd,
                        SimcoreS3FileID(
                            f"{dst_project_uuid}/{new_node_id}/{src_fmd.object_name.split('/')[-1]}"
                        ),
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
                    )
                    for output in node.get("outputs", {}).values()
                    if int(output.get("store", SIMCORE_S3_ID)) == DATCORE_ID
                ]
            )
        for task in copy_tasks:
            await task
        # NOTE: running this in parallel tends to block while testing. not sure why?
        # await asyncio.gather(*copy_tasks)

    # SEARCH -------------------------------------

    async def search_files_starting_with(
        self, user_id: UserID, prefix: str
    ) -> list[FileMetaData]:
        # Avoids using list_files since it accounts for projects/nodes
        # Storage should know NOTHING about those concepts
        async with self.engine.acquire() as conn, conn.begin():
            # access layer
            can_read_projects_ids = await get_readable_project_ids(conn, user_id)
            files_meta: list[
                FileMetaDataAtDB
            ] = await db_file_meta_data.list_fmds_with_partial_file_id(
                conn,
                user_id=user_id,
                project_ids=can_read_projects_ids,
                file_id_prefix=prefix,
                partial_file_id=None,
            )
            return [convert_db_to_model(fmd) for fmd in files_meta]

    async def create_soft_link(
        self, user_id: int, target_file_id: StorageFileID, link_file_id: StorageFileID
    ) -> FileMetaData:
        # validate link_uuid
        async with self.engine.acquire() as conn:
            if await db_file_meta_data.fmd_exists(
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
            return convert_db_to_model(
                await db_file_meta_data.insert_file_metadata(conn, target)
            )

    async def synchronise_meta_data_table(self, dry_run: bool) -> list[StorageFileID]:
        logger.warning(
            "synchronisation of database/s3 storage started, this will take some time..."
        )
        file_ids_to_remove = []
        async with self.engine.acquire() as conn:
            number_of_rows_in_db = await db_file_meta_data.number_of_uploaded_fmds(conn)
            logger.warning(
                "Total number of entries to check %d",
                number_of_rows_in_db,
            )
            # iterate over all entries to check if there is a file in the S3 backend
            async for fmd in db_file_meta_data.list_all_uploaded_fmds(conn):
                # SEE https://www.peterbe.com/plog/fastest-way-to-find-out-if-a-file-exists-in-s3
                if not await get_s3_client(self.app).list_files(
                    self.simcore_bucket_name, prefix=fmd.object_name
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
                self._update_database_from_storage_no_connection(
                    fmd.file_id,
                    fmd.bucket_name,
                    fmd.object_name,
                )
                for fmd in list_of_expired_uploads
            ),
            reraise=False,
            log=logger,
            max_concurrency=2,
        )
        list_of_fmds_to_delete = [
            expired_fmd
            for expired_fmd, updated_fmd in zip(list_of_expired_uploads, updated_fmds)
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
                max_concurrency=2,
            )
            logger.warning(
                "pending/incomplete uploads of [%s] removed",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )

    async def clean_expired_uploads(self) -> None:
        await self._clean_expired_uploads()

    async def _update_database_from_storage(
        self,
        conn: SAConnection,
        file_id: SimcoreS3FileID,
        bucket: S3BucketName,
        key: SimcoreS3FileID,
    ) -> FileMetaDataAtDB:
        s3_metadata = await get_s3_client(self.app).get_file_metadata(bucket, key)
        fmd = await db_file_meta_data.get(conn, file_id)
        fmd.file_size = parse_obj_as(ByteSize, s3_metadata.size)
        fmd.last_modified = s3_metadata.last_modified
        fmd.entity_tag = s3_metadata.e_tag
        fmd.upload_expires_at = None
        updated_fmd = await db_file_meta_data.upsert_file_metadata_for_upload(
            conn, convert_db_to_model(fmd)
        )
        return updated_fmd

    async def _update_database_from_storage_no_connection(
        self,
        file_id: SimcoreS3FileID,
        bucket: S3BucketName,
        key: SimcoreS3FileID,
    ) -> FileMetaDataAtDB:
        async with self.engine.acquire() as conn:
            updated_fmd = await self._update_database_from_storage(
                conn, file_id, bucket, key
            )
        return updated_fmd

    async def _copy_file_datcore_s3(
        self,
        user_id: UserID,
        source_uuid: str,
        dest_project_id: ProjectID,
        dest_node_id: NodeID,
        file_storage_link: dict[str, Any],
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
            # FIXME: connect download and upload streams
            local_file_path = Path(tmpdir) / filename
            # Downloads DATCore -> local
            await download_to_file_or_raise(session, dc_link, local_file_path)

            upload_expiration_date = datetime.datetime.utcnow() + datetime.timedelta(
                seconds=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS
            )
            # copying will happen using aioboto3, therefore multipart might happen
            new_fmd = FileMetaData.from_simcore_node(
                user_id,
                dst_file_id,
                self.simcore_bucket_name,
                self.location_id,
                self.location_name,
                upload_expires_at=upload_expiration_date,
            )
            async with self.engine.acquire() as conn, conn.begin():
                new_fmd = await db_file_meta_data.upsert_file_metadata_for_upload(
                    conn, new_fmd
                )
                # Uploads local -> S3
                await get_s3_client(self.app).upload_file(
                    self.simcore_bucket_name, local_file_path, dst_file_id
                )
                updated_fmd = await self._update_database_from_storage(
                    conn,
                    new_fmd.file_id,
                    new_fmd.bucket_name,
                    new_fmd.object_name,
                )
                file_storage_link["store"] = SIMCORE_S3_ID
                file_storage_link["path"] = new_fmd.file_id

                logger.info("copied %s to %s", f"{source_uuid=}", f"{updated_fmd=}")

        return convert_db_to_model(updated_fmd)

    async def _copy_file_s3_s3(
        self, user_id: UserID, src_fmd: FileMetaDataAtDB, dst_file_id: SimcoreS3FileID
    ) -> FileMetaData:
        logger.debug("copying %s to %s", f"{src_fmd=}", f"{dst_file_id=}")
        upload_expiration_date = datetime.datetime.utcnow() + datetime.timedelta(
            seconds=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS
        )
        # copying will happen using aioboto3, therefore multipart might happen
        new_fmd = FileMetaData.from_simcore_node(
            user_id,
            dst_file_id,
            self.simcore_bucket_name,
            self.location_id,
            self.location_name,
            upload_expires_at=upload_expiration_date,
        )

        async with self.engine.acquire() as conn, conn.begin():
            new_fmd = await db_file_meta_data.upsert_file_metadata_for_upload(
                conn, new_fmd
            )
            await get_s3_client(self.app).copy_file(
                self.simcore_bucket_name,
                src_fmd.object_name,
                new_fmd.object_name,
            )
            updated_fmd = await self._update_database_from_storage(
                conn,
                new_fmd.file_id,
                new_fmd.bucket_name,
                new_fmd.object_name,
            )
        logger.info("copied %s to %s", f"{src_fmd=}", f"{updated_fmd=}")
        return convert_db_to_model(updated_fmd)


def create_simcore_s3_data_manager(app: web.Application) -> SimcoreS3DataManager:
    cfg: Settings = app[APP_CONFIG_KEY]
    assert cfg.STORAGE_S3  # nosec
    return SimcoreS3DataManager(
        engine=app[APP_DB_ENGINE_KEY],
        simcore_bucket_name=parse_obj_as(S3BucketName, cfg.STORAGE_S3.S3_BUCKET_NAME),
        app=app,
        settings=cfg,
    )
