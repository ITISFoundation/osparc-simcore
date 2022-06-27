import asyncio
import dataclasses
import datetime
import logging
import tempfile
import urllib.parse
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Final, Optional, Union

from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from models_library.api_schemas_storage import LinkType, S3BucketName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import (
    LocationName,
    NodeID,
    SimcoreS3FileID,
    StorageFileID,
)
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, parse_obj_as
from servicelib.aiohttp.aiopg_utils import PostgresRetryPolicyUponOperation
from servicelib.aiohttp.client_session import get_client_session
from simcore_service_storage.s3 import get_s3_client
from yarl import URL

from . import db_file_meta_data, db_projects
from .constants import (
    APP_CONFIG_KEY,
    APP_DB_ENGINE_KEY,
    APP_DSM_KEY,
    DATCORE_ID,
    DATCORE_STR,
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
from .exceptions import FileMetaDataNotFoundError, S3KeyNotFoundError
from .models import DatasetMetaData, DatCoreApiToken, FileMetaData, file_meta_data
from .settings import Settings
from .utils import download_to_file_or_raise, is_file_entry_valid

_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE


logger = logging.getLogger(__name__)

postgres_service_retry_policy_kwargs = PostgresRetryPolicyUponOperation(logger).kwargs


def setup_dsm(app: web.Application):
    async def _cleanup_context(app: web.Application):
        cfg: Settings = app[APP_CONFIG_KEY]
        assert cfg.STORAGE_S3  # nosec
        dsm = DataStorageManager(
            engine=app[APP_DB_ENGINE_KEY],
            simcore_bucket_name=S3BucketName(cfg.STORAGE_S3.S3_BUCKET_NAME),
            app=app,
            settings=cfg,
        )

        app[APP_DSM_KEY] = dsm

        yield

        logger.info("Shuting down %s", f"{dsm=}")

    # ------

    app.cleanup_ctx.append(_cleanup_context)


@dataclass
class DataStorageManager:  # pylint: disable=too-many-public-methods
    """Data storage manager

    The dsm has access to the database for all meta data and to the actual backend. For now this
    is simcore's S3 [minio] and the datcore storage facilities.

    For all data that is in-house (simcore.s3, ...) we keep a synchronized database with meta information
    for the physical files.

    For physical changes on S3, that might be time-consuming, the db keeps a state (delete and upload mostly)

    The dsm provides the following additional functionalities:

    - listing of folders for a given users, optionally filtered using a regular expression and optionally
      sorted by one of the meta data keys

    - upload/download of files

        client -> S3 : presigned upload link
        S3 -> client : presigned download link
        datcore -> client: presigned download link
        S3 -> datcore: local copy and then upload via their api

    minio/S3 and postgres can talk nicely with each other via Notifications using rabbigMQ which we already have.
    See:

        https://blog.minio.io/part-5-5-publish-minio-events-via-postgresql-50f6cc7a7346
        https://docs.minio.io/docs/minio-bucket-notification-guide.html
    """

    engine: Engine
    simcore_bucket_name: S3BucketName
    app: web.Application
    settings: Settings
    datcore_tokens: dict[UserID, DatCoreApiToken] = field(default_factory=dict)

    def _get_datcore_tokens(
        self, user_id: UserID
    ) -> tuple[Optional[str], Optional[str]]:
        token = self.datcore_tokens.get(user_id, DatCoreApiToken())
        return dataclasses.astuple(token)

    async def locations(self, user_id: UserID):
        locs = []
        simcore_s3 = {"name": SIMCORE_S3_STR, "id": SIMCORE_S3_ID}
        locs.append(simcore_s3)

        api_token, api_secret = self._get_datcore_tokens(user_id)

        if api_token and api_secret and self.app:
            if await datcore_adapter.check_user_can_connect(
                self.app, api_token, api_secret
            ):
                datcore = {"name": DATCORE_STR, "id": DATCORE_ID}
                locs.append(datcore)

        return locs

    # LIST/GET ---------------------------

    async def list_files(  # pylint: disable=too-many-branches, disable=too-many-statements
        self, user_id: UserID, location: LocationName, uuid_filter: str = ""
    ) -> list[FileMetaData]:

        """Returns a list of file paths

        - Works for simcore.s3 and datcore
        - Can filter on uuid: useful to filter on project_id/node_id
        """
        data: deque[FileMetaData] = deque()
        if location == SIMCORE_S3_STR:
            accesible_projects_ids = []
            async with self.engine.acquire() as conn, conn.begin():
                accesible_projects_ids = await get_readable_project_ids(conn, user_id)
                file_metadatas = await db_file_meta_data.list_fmds_with_partial_file_id(
                    conn,
                    user_id=user_id,
                    project_ids=accesible_projects_ids,
                    file_id_prefix=None,
                    partial_file_id=uuid_filter,
                )

                for fmd in file_metadatas:
                    if is_file_entry_valid(fmd):
                        data.append(fmd)
                        continue
                    with suppress(S3KeyNotFoundError):
                        # 1. this was uploaded using the legacy file upload that relied on
                        # a background task checking the S3 backend unreliably, the file eventually
                        # will be uploaded and this will lazily update the database
                        # 2. this is still in upload and the file is missing and it will raise
                        updated_fmd = await self.update_database_from_storage(
                            conn, fmd.file_id, fmd.bucket_name, fmd.object_name
                        )
                        data.append(updated_fmd)

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

        if location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            return await datcore_adapter.list_all_datasets_files_metadatas(
                self.app, user_id, api_token, api_secret
            )

    async def list_files_dataset(
        self, user_id: UserID, location: LocationName, dataset_id: str
    ) -> list[FileMetaData]:
        # this is a cheap shot, needs fixing once storage/db is in sync
        data = []
        if location == SIMCORE_S3_STR:
            data: list[FileMetaData] = await self.list_files(
                user_id, location, uuid_filter=dataset_id + "/"
            )

        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            # lists all the files inside the dataset
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            return await datcore_adapter.list_all_files_metadatas_in_dataset(
                self.app, user_id, api_token, api_secret, dataset_id
            )

        return data

    async def list_datasets(
        self, user_id: UserID, location: LocationName
    ) -> list[DatasetMetaData]:
        """Returns a list of top level datasets

        Works for simcore.s3 and datcore

        """
        if location == SIMCORE_S3_STR:
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

        if location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            return await datcore_adapter.list_datasets(self.app, api_token, api_secret)

        raise NotImplementedError("Invalid location")

    async def list_file(
        self, user_id: UserID, location: LocationName, file_id: StorageFileID
    ) -> Optional[FileMetaData]:

        if location == SIMCORE_S3_STR:

            async with self.engine.acquire() as conn, conn.begin():
                can: Optional[AccessRights] = await get_file_access_rights(
                    conn, int(user_id), file_id
                )
                if can.read:
                    try:
                        file_metadata = await db_file_meta_data.get(conn, file_id)
                        if not is_file_entry_valid(file_metadata):
                            file_metadata = await self.update_database_from_storage(
                                conn,
                                file_id,
                                file_meta_data.bucket_name,
                                file_meta_data.object_name,
                            )
                        return file_metadata
                    except FileMetaDataNotFoundError:
                        # NOTE: backward compatible code...
                        return None
                    except S3KeyNotFoundError:
                        # the user has not uploaded anything yet
                        return None
                logger.debug("User %s cannot read file %s", user_id, file_id)
                return None

        if location == DATCORE_STR:
            raise NotImplementedError

    # UPLOAD/DOWNLOAD LINKS ---------------------------

    async def update_database_from_storage(
        self,
        conn: SAConnection,
        file_id: SimcoreS3FileID,
        bucket: S3BucketName,
        key: SimcoreS3FileID,
    ) -> FileMetaData:
        s3_metadata = await get_s3_client(self.app).get_file_metadata(bucket, key)
        fmd = await db_file_meta_data.get(conn, file_id)
        fmd.file_size = parse_obj_as(ByteSize, s3_metadata.size)
        fmd.last_modified = s3_metadata.last_modified
        fmd.entity_tag = s3_metadata.e_tag
        fmd.upload_expires_at = None
        updated_fmd = await db_file_meta_data.upsert_file_metadata_for_upload(conn, fmd)
        return updated_fmd

    async def try_update_database_from_storage(
        self,
        file_id: SimcoreS3FileID,
        bucket: S3BucketName,
        key: SimcoreS3FileID,
        *,
        reraise_exceptions: bool = True,
    ) -> Optional[FileMetaData]:
        try:
            async with self.engine.acquire() as conn:
                updated_fmd = await self.update_database_from_storage(
                    conn, file_id, bucket, key
                )
            return updated_fmd
        except S3KeyNotFoundError:
            logger.warning("Could not access %s in S3 backend", f"{file_id=}")
            if reraise_exceptions:
                raise
        except FileMetaDataNotFoundError:
            logger.warning(
                "Could not find %s in database, but present in S3 backend. TIP: check this should not happen",
                f"{file_id=}",
            )
            if reraise_exceptions:
                raise

    async def create_upload_link(
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
                file_id=file_id,
                bucket=self.simcore_bucket_name,
                upload_expires_at=upload_expiration_date,
            )
            await db_file_meta_data.upsert_file_metadata_for_upload(conn, fmd)

            # return the appropriate links
            if link_type == LinkType.PRESIGNED:
                single_presigned_link = await get_s3_client(
                    self.app
                ).create_single_presigned_upload_link(
                    self.simcore_bucket_name,
                    file_id,
                    expiration_secs=self.settings.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS,
                )
                return parse_obj_as(AnyUrl, f"{single_presigned_link}")

        # user wants just the s3 link
        s3_link = get_s3_client(self.app).compute_s3_url(
            self.simcore_bucket_name, file_id
        )
        return s3_link

    async def abort_upload(self, file_id: StorageFileID, user_id: UserID) -> None:
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
            file: FileMetaData = await db_file_meta_data.get(conn, file_id)

            try:
                # try to revert to what we have in storage
                await self.update_database_from_storage(
                    conn,
                    file.file_id,
                    file.bucket_name,
                    file.object_name,
                )
            except S3KeyNotFoundError:
                # the file does not exist, so we delete the entry
                async with self.engine.acquire() as conn:
                    await db_file_meta_data.delete(conn, [file_id])

    async def download_link_s3(
        self, file_id: StorageFileID, user_id: UserID, link_type: LinkType
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

        fmd = await db_file_meta_data.get(conn, file_id)

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

    async def download_link_datcore(self, user_id: UserID, file_id: str) -> URL:
        api_token, api_secret = self._get_datcore_tokens(user_id)
        assert self.app  # nosec
        assert api_secret  # nosec
        assert api_token  # nosec
        return await datcore_adapter.get_file_download_presigned_link(
            self.app, api_token, api_secret, file_id
        )

    # COPY -----------------------------

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
        dc_link = await self.download_link_datcore(user_id, source_uuid)
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
                upload_expires_at=upload_expiration_date,
            )
            async with self.engine.acquire() as conn, conn.begin():
                await db_file_meta_data.upsert_file_metadata_for_upload(conn, new_fmd)
                # Uploads local -> S3
                await get_s3_client(self.app).upload_file(
                    self.simcore_bucket_name, local_file_path, dst_file_id
                )
                updated_fmd = await self.update_database_from_storage(
                    conn,
                    new_fmd.file_id,
                    new_fmd.bucket_name,
                    new_fmd.object_name,
                )
                file_storage_link["store"] = SIMCORE_S3_ID
                file_storage_link["path"] = new_fmd.file_id

                logger.info("copied %s to %s", f"{source_uuid=}", f"{updated_fmd=}")

        return updated_fmd

    async def _copy_file_s3_s3(
        self, user_id: UserID, src_fmd: FileMetaData, dst_file_id: SimcoreS3FileID
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
            upload_expires_at=upload_expiration_date,
        )

        async with self.engine.acquire() as conn, conn.begin():
            await db_file_meta_data.upsert_file_metadata_for_upload(conn, new_fmd)
            await get_s3_client(self.app).copy_file(
                self.simcore_bucket_name,
                src_fmd.object_name,
                new_fmd.object_name,
            )
            updated_fmd = await self.update_database_from_storage(
                conn,
                new_fmd.file_id,
                new_fmd.bucket_name,
                new_fmd.object_name,
            )
        logger.info("copied %s to %s", f"{src_fmd=}", f"{updated_fmd=}")
        return updated_fmd

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
            src_project_files: list[FileMetaData] = await db_file_meta_data.list_fmds(
                conn, project_ids=[src_project_uuid]
            )

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
                            f"{dst_project_uuid}/{new_node_id}/{src_fmd.file_name}"
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

    # DELETE -------------------------------------
    async def delete_file(
        self, user_id: UserID, location: LocationName, file_id: StorageFileID
    ):
        """Deletes a file given its fmd and location

        Additionally requires a user_id for 3rd party auth

        For internal storage, the db state should be updated upon completion via
        Notification mechanism

        For simcore.s3 we can use the file_name
        For datcore we need the full path
        """
        if location == SIMCORE_S3_STR:
            async with self.engine.acquire() as conn, conn.begin():
                can: Optional[AccessRights] = await get_file_access_rights(
                    conn, user_id, file_id
                )
                if not can.delete:
                    raise web.HTTPForbidden(
                        reason=f"User {user_id} does not have enough access rights to delete file {file_id}"
                    )
                with suppress(FileMetaDataNotFoundError):
                    file: FileMetaData = await db_file_meta_data.get(conn, file_id)
                    # deleting a non existing file simply works
                    await get_s3_client(self.app).delete_file(
                        file.bucket_name, file.file_id
                    )

        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            await datcore_adapter.delete_file(self.app, api_token, api_secret, file_id)

    async def delete_project_simcore_s3(
        self, user_id: UserID, project_id: ProjectID, node_id: Optional[NodeID] = None
    ) -> Optional[web.Response]:

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

    # SEARCH -------------------------------------

    async def search_files_starting_with(
        self, user_id: UserID, prefix: str
    ) -> list[FileMetaData]:
        # Avoids using list_files since it accounts for projects/nodes
        # Storage should know NOTHING about those concepts
        async with self.engine.acquire() as conn, conn.begin():
            # access layer
            can_read_projects_ids = await get_readable_project_ids(conn, user_id)
            files_meta = await db_file_meta_data.list_fmds_with_partial_file_id(
                conn,
                user_id=user_id,
                project_ids=can_read_projects_ids,
                file_id_prefix=prefix,
                partial_file_id=None,
            )
            return files_meta

    async def create_soft_link(
        self, user_id: int, target_file_id: StorageFileID, link_file_id: StorageFileID
    ) -> FileMetaData:

        # validate link_uuid
        async with self.engine.acquire() as conn:
            if db_file_meta_data.fmd_exists(conn, link_file_id):
                raise web.HTTPUnprocessableEntity(
                    reason=f"Invalid link {link_file_id}. Link already exists"
                )

        # validate target_uuid
        target = await self.list_file(user_id, SIMCORE_S3_STR, target_file_id)
        if not target:
            raise web.HTTPNotFound(
                reason=f"Invalid target '{target_file_id}'. File does not exists for this user"
            )

        # duplicate target and change the following columns:
        target.file_uuid = link_file_id
        target.file_id = link_file_id  # NOTE: api-server relies on this id
        target.is_soft_link = True

        async with self.engine.acquire() as conn:
            return await db_file_meta_data.insert_file_metadata(conn, target)

    async def synchronise_meta_data_table(
        self, location: LocationName, dry_run: bool
    ) -> list[StorageFileID]:
        assert (  # nosec
            location == SIMCORE_S3_STR
        ), "Only with s3, no other sync implemented"  # nosec

        if location == SIMCORE_S3_STR:

            # NOTE: only valid for simcore, since datcore data is not in the database table
            # let's get all the files in the table
            logger.warning(
                "synchronisation of database/s3 storage started, this will take some time..."
            )
            file_ids_to_remove: list[StorageFileID] = []
            async with self.engine.acquire() as conn:
                number_of_rows_in_db = await db_file_meta_data.number_of_uploaded_fmds(
                    conn
                )
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

        # try first to upload these from S3 (conservative)
        updated_fmds = await asyncio.gather(
            *(
                self.try_update_database_from_storage(
                    fmd.file_id,
                    fmd.bucket_name,
                    fmd.object_name,
                )
                for fmd in list_of_expired_uploads
            ),
            return_exceptions=True,
        )
        list_of_fmds_to_delete = [
            expired_fmd
            for expired_fmd, updated_fmd in zip(list_of_expired_uploads, updated_fmds)
            if not isinstance(updated_fmd, FileMetaData)
        ]
        if list_of_fmds_to_delete:
            # delete the remaining ones
            logger.debug(
                "following unfinished/incomplete uploads will now be deleted : [%s]",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )
            await asyncio.gather(
                *(
                    self.delete_file(fmd.user_id, fmd.location, fmd.file_id)
                    for fmd in list_of_fmds_to_delete
                    if fmd.user_id is not None
                )
            )
            logger.warning(
                "pending/incomplete uploads of [%s] removed",
                [fmd.file_id for fmd in list_of_fmds_to_delete],
            )

    async def clean_expired_uploads(self) -> None:
        await self._clean_expired_uploads()
