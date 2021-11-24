# pylint: disable=no-value-for-parameter
# FIXME: E1120:No value for argument 'dml' in method call
# pylint: disable=protected-access
# FIXME: Access to a protected member _result_proxy of a client class

import asyncio
import logging
import os
import re
import tempfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Tuple, Union

import aiobotocore
import attr
import botocore
import sqlalchemy as sa
from aiobotocore.client import AioBaseClient
from aiobotocore.session import AioSession, ClientCreatorContext
from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from servicelib.aiohttp.aiopg_utils import DBAPIError, PostgresRetryPolicyUponOperation
from servicelib.aiohttp.client_session import get_client_session
from servicelib.utils import fire_and_forget_task
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.expression import literal_column
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type, retry_if_result
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_exponential
from yarl import URL

from .access_layer import (
    AccessRights,
    get_file_access_rights,
    get_project_access_rights,
    get_readable_project_ids,
)
from .constants import (
    APP_CONFIG_KEY,
    APP_DB_ENGINE_KEY,
    APP_DSM_KEY,
    APP_S3_KEY,
    DATCORE_ID,
    DATCORE_STR,
    SIMCORE_S3_ID,
    SIMCORE_S3_STR,
)
from .datcore_adapter import datcore_adapter
from .models import (
    DatasetMetaData,
    FileMetaData,
    FileMetaDataEx,
    file_meta_data,
    get_location_from_id,
    projects,
)
from .s3wrapper.s3_client import MinioClientWrapper
from .settings import Settings
from .utils import download_to_file_or_raise, is_file_entry_valid, to_meta_data_extended

_MINUTE: Final[int] = 60
_HOUR: Final[int] = 60 * _MINUTE


logger = logging.getLogger(__name__)

postgres_service_retry_policy_kwargs = PostgresRetryPolicyUponOperation(logger).kwargs


def setup_dsm(app: web.Application):
    async def _cleanup_context(app: web.Application):
        cfg: Settings = app[APP_CONFIG_KEY]

        with ThreadPoolExecutor(max_workers=cfg.STORAGE_MAX_WORKERS) as executor:
            dsm = DataStorageManager(
                s3_client=app.get(APP_S3_KEY),
                engine=app.get(APP_DB_ENGINE_KEY),
                loop=asyncio.get_event_loop(),
                pool=executor,
                simcore_bucket_name=cfg.STORAGE_S3.S3_BUCKET_NAME,
                has_project_db=not cfg.STORAGE_TESTING,
                app=app,
            )  # type: ignore

            app[APP_DSM_KEY] = dsm

            yield

            assert app[APP_DSM_KEY].pool is executor  # nosec

            logger.info("Shuting down %s", dsm.pool)

    # ------

    app.cleanup_ctx.append(_cleanup_context)


@dataclass
class DatCoreApiToken:
    api_token: Optional[str] = None
    api_secret: Optional[str] = None

    def to_tuple(self):
        return (self.api_token, self.api_secret)


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

    # TODO: perhaps can be used a cache? add a lifetime?

    s3_client: MinioClientWrapper
    engine: Engine
    loop: object
    pool: ThreadPoolExecutor
    simcore_bucket_name: str
    has_project_db: bool
    session: AioSession = field(default_factory=aiobotocore.get_session)
    datcore_tokens: Dict[str, DatCoreApiToken] = field(default_factory=dict)
    app: Optional[web.Application] = None

    def _create_aiobotocore_client_context(self) -> ClientCreatorContext:
        assert hasattr(self.session, "create_client")  # nosec
        # pylint: disable=no-member

        # SEE API in https://botocore.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html
        # SEE https://aiobotocore.readthedocs.io/en/latest/index.html
        return self.session.create_client(
            "s3",
            endpoint_url=self.s3_client.endpoint_url,
            aws_access_key_id=self.s3_client.access_key,
            aws_secret_access_key=self.s3_client.secret_key,
        )

    def _get_datcore_tokens(self, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        # pylint: disable=no-member
        token = self.datcore_tokens.get(user_id, DatCoreApiToken())
        return token.to_tuple()

    async def locations(self, user_id: str):
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

    @classmethod
    def location_from_id(cls, location_id: str):
        return get_location_from_id(location_id)

    # LIST/GET ---------------------------

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    async def list_files(
        self, user_id: str, location: str, uuid_filter: str = "", regex: str = ""
    ) -> List[FileMetaDataEx]:
        """Returns a list of file paths

        - Works for simcore.s3 and datcore
        - Can filter on uuid: useful to filter on project_id/node_id
        - Can filter upon regular expression (for now only on key: value pairs of the FileMetaData)
        """
        data = deque()
        if location == SIMCORE_S3_STR:
            accesible_projects_ids = []
            async with self.engine.acquire() as conn, conn.begin():
                accesible_projects_ids = await get_readable_project_ids(
                    conn, int(user_id)
                )
                where_statement = (
                    file_meta_data.c.user_id == user_id
                ) | file_meta_data.c.project_id.in_(accesible_projects_ids)
                if uuid_filter:
                    where_statement &= file_meta_data.c.file_uuid.ilike(
                        f"%{uuid_filter}%"
                    )
                query = sa.select([file_meta_data]).where(where_statement)

                async for row in conn.execute(query):
                    dex = to_meta_data_extended(row)
                    if not is_file_entry_valid(dex.fmd):
                        # NOTE: the file is not updated with the information from S3 backend.
                        # 1. Either the file exists, but was never updated in the database
                        # 2. Or the file does not exist or was never completed, and the file_meta_data entry is old and faulty
                        # we need to update from S3 here since the database is not up-to-date
                        dex = await self.try_update_database_from_storage(
                            dex.fmd.file_uuid,
                            dex.fmd.bucket_name,
                            dex.fmd.object_name,
                        )
                    if dex:
                        data.append(dex)

            if self.has_project_db:
                uuid_name_dict = {}
                # now parse the project to search for node/project names
                try:
                    async with self.engine.acquire() as conn, conn.begin():
                        query = sa.select([projects]).where(
                            projects.c.uuid.in_(accesible_projects_ids)
                        )

                        async for row in conn.execute(query):
                            proj_data = dict(row.items())

                            uuid_name_dict[proj_data["uuid"]] = proj_data["name"]
                            wb = proj_data["workbench"]
                            for node in wb.keys():
                                uuid_name_dict[node] = wb[node]["label"]
                except DBAPIError as _err:
                    logger.exception("Error querying database for project names")

                if not uuid_name_dict:
                    # there seems to be no project whatsoever for user_id
                    return []

                # only keep files from non-deleted project
                clean_data = deque()
                for dx in data:
                    d = dx.fmd
                    if d.project_id not in uuid_name_dict:
                        continue
                    #
                    # FIXME: artifically fills ['project_name', 'node_name', 'file_id', 'raw_file_path', 'display_file_path']
                    #        with information from the projects table!

                    d.project_name = uuid_name_dict[d.project_id]
                    if d.node_id in uuid_name_dict:
                        d.node_name = uuid_name_dict[d.node_id]

                    d.raw_file_path = str(
                        Path(d.project_id) / Path(d.node_id) / Path(d.file_name)
                    )
                    d.display_file_path = d.raw_file_path
                    d.file_id = d.file_uuid
                    if d.node_name and d.project_name:
                        d.display_file_path = str(
                            Path(d.project_name) / Path(d.node_name) / Path(d.file_name)
                        )
                        # once the data was sync to postgres metadata table at this point
                        clean_data.append(dx)

                data = clean_data

        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            return await datcore_adapter.list_all_datasets_files_metadatas(
                self.app, api_token, api_secret
            )

        if uuid_filter:
            # TODO: incorporate this in db query!
            _query = re.compile(uuid_filter, re.IGNORECASE)
            filtered_data = deque()
            for dx in data:
                d = dx.fmd
                if _query.search(d.file_uuid):
                    filtered_data.append(dx)

            return list(filtered_data)

        if regex:
            _query = re.compile(regex, re.IGNORECASE)
            filtered_data = deque()
            for dx in data:
                d = dx.fmd
                _vars = vars(d)
                for v in _vars.keys():
                    if _query.search(v) or _query.search(str(_vars[v])):
                        filtered_data.append(dx)
                        break
            return list(filtered_data)

        return list(data)

    async def list_files_dataset(
        self, user_id: str, location: str, dataset_id: str
    ) -> Union[List[FileMetaData], List[FileMetaDataEx]]:
        # this is a cheap shot, needs fixing once storage/db is in sync
        data = []
        if location == SIMCORE_S3_STR:
            data: List[FileMetaDataEx] = await self.list_files(
                user_id, location, uuid_filter=dataset_id + "/"
            )

        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            # lists all the files inside the dataset
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            return await datcore_adapter.list_all_files_metadatas_in_dataset(
                self.app, api_token, api_secret, dataset_id
            )

        return data

    async def list_datasets(self, user_id: str, location: str) -> List[DatasetMetaData]:
        """Returns a list of top level datasets

        Works for simcore.s3 and datcore

        """
        data = []

        if location == SIMCORE_S3_STR:
            if self.has_project_db:
                try:
                    async with self.engine.acquire() as conn, conn.begin():
                        readable_projects_ids = await get_readable_project_ids(
                            conn, int(user_id)
                        )
                        has_read_access = projects.c.uuid.in_(readable_projects_ids)

                        # FIXME: this DOES NOT read from file-metadata table!!!
                        query = sa.select([projects.c.uuid, projects.c.name]).where(
                            has_read_access
                        )
                        async for row in conn.execute(query):
                            dmd = DatasetMetaData(
                                dataset_id=row.uuid,
                                display_name=row.name,
                            )
                            data.append(dmd)
                except DBAPIError as _err:
                    logger.exception("Error querying database for project names")

        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            return await datcore_adapter.list_datasets(self.app, api_token, api_secret)

        return data

    async def list_file(
        self, user_id: str, location: str, file_uuid: str
    ) -> Optional[FileMetaDataEx]:

        if location == SIMCORE_S3_STR:

            async with self.engine.acquire() as conn, conn.begin():
                can: Optional[AccessRights] = await get_file_access_rights(
                    conn, int(user_id), file_uuid
                )
                if can.read:
                    query = sa.select([file_meta_data]).where(
                        file_meta_data.c.file_uuid == file_uuid
                    )
                    result = await conn.execute(query)
                    row = await result.first()
                    if not row:
                        return None
                    file_metadata = to_meta_data_extended(row)
                    if is_file_entry_valid(file_metadata.fmd):
                        return file_metadata
                    # we need to update from S3 here since the database is not up-to-date
                    file_metadata = await self.try_update_database_from_storage(
                        file_metadata.fmd.file_uuid,
                        file_metadata.fmd.bucket_name,
                        file_metadata.fmd.object_name,
                    )
                    return file_metadata
                # FIXME: returns None in both cases: file does not exist or use has no access
                logger.debug("User %s cannot read file %s", user_id, file_uuid)
                return None

        elif location == DATCORE_STR:
            # FIXME: review return inconsistencies
            # api_token, api_secret = self._get_datcore_tokens(user_id)
            import warnings

            warnings.warn("NOT IMPLEMENTED!!!")
            return None

    # UPLOAD/DOWNLOAD LINKS ---------------------------

    async def upload_file_to_datcore(
        self, _user_id: str, _local_file_path: str, _destination_id: str
    ):
        import warnings

        warnings.warn(f"NOT IMPLEMENTED!!! in {self.__class__}")
        # uploads a locally available file to dat core given the storage path, optionally attached some meta data
        # api_token, api_secret = self._get_datcore_tokens(user_id)
        # await dcw.upload_file_to_id(destination_id, local_file_path)

    async def try_update_database_from_storage(
        self,
        file_uuid: str,
        bucket_name: str,
        object_name: str,
        silence_exception: bool = False,
    ) -> Optional[FileMetaDataEx]:
        try:
            async with self._create_aiobotocore_client_context() as aioboto_client:
                result = await aioboto_client.head_object(
                    Bucket=bucket_name, Key=object_name
                )  # type: ignore

                file_size = result["ContentLength"]  # type: ignore
                last_modified = result["LastModified"]  # type: ignore
                entity_tag = result["ETag"].strip('"')  # type: ignore

                async with self.engine.acquire() as conn:
                    result: ResultProxy = await conn.execute(
                        file_meta_data.update()
                        .where(file_meta_data.c.file_uuid == file_uuid)
                        .values(
                            file_size=file_size,
                            last_modified=last_modified,
                            entity_tag=entity_tag,
                        )
                        .returning(literal_column("*"))
                    )
                    if not result:
                        return None
                    row: Optional[RowProxy] = await result.first()
                    if not row:
                        return None

                    return to_meta_data_extended(row)
        except botocore.exceptions.ClientError:
            if silence_exception:
                logger.debug("Error happened while trying to access %s", file_uuid)
            else:
                logger.warning(
                    "Error happened while trying to access %s", file_uuid, exc_info=True
                )
            # the file is not existing or some error happened
            return None

    @retry(
        stop=stop_after_delay(1 * _HOUR),
        wait=wait_exponential(multiplier=0.1, exp_base=1.2, max=30),
        retry=(
            retry_if_exception_type() | retry_if_result(lambda result: result is None)
        ),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    async def auto_update_database_from_storage_task(
        self, file_uuid: str, bucket_name: str, object_name: str
    ):
        return await self.try_update_database_from_storage(
            file_uuid, bucket_name, object_name, silence_exception=True
        )

    async def upload_link(self, user_id: str, file_uuid: str):
        """
        Creates pre-signed upload link and updates metadata table when
        link is used and upload is successfuly completed

        SEE _metadata_file_updater
        """

        async with self.engine.acquire() as conn:
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_uuid
            )
            if not can.write:
                logger.debug(
                    "User %s was not allowed to upload file %s", user_id, file_uuid
                )
                raise web.HTTPForbidden(
                    reason=f"User does not have enough access rights to upload file {file_uuid}"
                )

        @retry(**postgres_service_retry_policy_kwargs)
        async def _init_metadata() -> Tuple[int, str]:
            async with self.engine.acquire() as conn:
                fmd = FileMetaData()
                fmd.simcore_from_uuid(file_uuid, self.simcore_bucket_name)
                fmd.user_id = user_id  # NOTE: takes ownership of uploaded data

                # if file already exists, we might want to update a time-stamp

                # upsert file_meta_data
                insert_stmt = pg_insert(file_meta_data).values(**vars(fmd))
                do_nothing_stmt = insert_stmt.on_conflict_do_nothing(
                    index_elements=["file_uuid"]
                )
                await conn.execute(do_nothing_stmt)

                return fmd.file_size, fmd.last_modified

        await _init_metadata()

        bucket_name = self.simcore_bucket_name
        object_name = file_uuid

        # a parallel task is tarted which will update the metadata of the updated file
        # once the update has finished.
        fire_and_forget_task(
            self.auto_update_database_from_storage_task(
                file_uuid=file_uuid,
                bucket_name=bucket_name,
                object_name=object_name,
            )
        )
        return self.s3_client.create_presigned_put_url(bucket_name, object_name)

    async def download_link_s3(self, file_uuid: str, user_id: int) -> str:

        # access layer
        async with self.engine.acquire() as conn:
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_uuid
            )
            if not can.read:
                # NOTE: this is tricky. A user with read access can download and data!
                # If write permission would be required, then shared projects as views cannot
                # recover data in nodes (e.g. jupyter cannot pull work data)
                #
                logger.debug(
                    "User %s was not allowed to download file %s", user_id, file_uuid
                )
                raise web.HTTPForbidden(
                    reason=f"User does not have enough rights to download {file_uuid}"
                )

        bucket_name = self.simcore_bucket_name
        async with self.engine.acquire() as conn:
            stmt = sa.select([file_meta_data.c.object_name]).where(
                file_meta_data.c.file_uuid == file_uuid
            )
            object_name: Optional[str] = await conn.scalar(stmt)

            if object_name is None:
                raise web.HTTPNotFound(
                    reason=f"File '{file_uuid}' does not exists in storage."
                )

        link = self.s3_client.create_presigned_get_url(bucket_name, object_name)
        return link

    async def download_link_datcore(self, user_id: str, file_id: str) -> URL:
        api_token, api_secret = self._get_datcore_tokens(user_id)
        assert self.app  # nosec
        assert api_secret  # nosec
        assert api_token  # nosec
        return await datcore_adapter.get_file_download_presigned_link(
            self.app, api_token, api_secret, file_id
        )

    # COPY -----------------------------

    async def copy_file_s3_s3(self, user_id: str, dest_uuid: str, source_uuid: str):
        # FIXME: operation MUST be atomic

        # source is s3, location is s3
        to_bucket_name = self.simcore_bucket_name
        to_object_name = dest_uuid
        from_bucket = self.simcore_bucket_name
        from_object_name = source_uuid
        # FIXME: This is not async!
        self.s3_client.copy_object(
            to_bucket_name, to_object_name, from_bucket, from_object_name
        )

        # update db
        async with self.engine.acquire() as conn:
            fmd = FileMetaData()
            fmd.simcore_from_uuid(dest_uuid, self.simcore_bucket_name)
            fmd.user_id = user_id
            ins = file_meta_data.insert().values(**vars(fmd))
            await conn.execute(ins)

    async def copy_file_s3_datcore(
        self, user_id: str, dest_uuid: str, source_uuid: str
    ):
        session = get_client_session(self.app)

        # source is s3, get link and copy to datcore
        bucket_name = self.simcore_bucket_name
        object_name = source_uuid
        filename = source_uuid.split("/")[-1]

        s3_dowload_link = self.s3_client.create_presigned_get_url(
            bucket_name, object_name
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # FIXME: connect download and upload streams
            local_file_path = os.path.join(tmpdir, filename)

            # Downloads S3 -> local
            await download_to_file_or_raise(session, s3_dowload_link, local_file_path)

            # Uploads local -> DATCore
            await self.upload_file_to_datcore(
                _user_id=user_id,
                _local_file_path=local_file_path,
                _destination_id=dest_uuid,
            )

    async def copy_file_datcore_s3(
        self,
        user_id: str,
        dest_uuid: str,
        source_uuid: str,
        filename_missing: bool = False,
    ):
        session = get_client_session(self.app)

        # 2 steps: Get download link for local copy, the upload link to s3
        # TODO: This should be a redirect stream!
        dc_link, filename = await self.download_link_datcore(
            user_id=user_id, file_id=source_uuid
        )
        if filename_missing:
            dest_uuid = str(Path(dest_uuid) / filename)

        s3_upload_link = await self.upload_link(user_id, dest_uuid)

        with tempfile.TemporaryDirectory() as tmpdir:
            # FIXME: connect download and upload streams

            local_file_path = os.path.join(tmpdir, filename)

            # Downloads DATCore -> local
            await download_to_file_or_raise(session, dc_link, local_file_path)

            # Uploads local -> S3
            s3_upload_link = URL(s3_upload_link)
            async with session.put(
                s3_upload_link,
                data=Path(local_file_path).open("rb"),
                raise_for_status=True,
            ) as resp:
                logger.debug(
                    "Uploaded local -> SIMCore %s . Status %s",
                    s3_upload_link,
                    resp.status,
                )

        return dest_uuid

    async def copy_file(
        self,
        user_id: str,
        dest_location: str,
        dest_uuid: str,
        source_location: str,
        source_uuid: str,
    ):
        if source_location == SIMCORE_S3_STR:
            if dest_location == DATCORE_STR:
                await self.copy_file_s3_datcore(user_id, dest_uuid, source_uuid)
            elif dest_location == SIMCORE_S3_STR:
                await self.copy_file_s3_s3(user_id, dest_uuid, source_uuid)
        elif source_location == DATCORE_STR:
            if dest_location == DATCORE_STR:
                raise NotImplementedError("copy files from datcore 2 datcore not impl")
            if dest_location == SIMCORE_S3_STR:
                await self.copy_file_datcore_s3(user_id, dest_uuid, source_uuid)

    async def deep_copy_project_simcore_s3(
        self,
        user_id: str,
        source_project: Dict[str, Any],
        destination_project: Dict[str, Any],
        node_mapping: Dict[str, str],
    ):
        """Parses a given source project and copies all related files to the destination project

        Since all files are organized as

            project_id/node_id/filename or links to datcore

        this function creates a new folder structure

            project_id/node_id/filename

        and copies all files to the corresponding places.

        Additionally, all external files from datcore are being copied and the paths in the destination
        project are adapted accordingly

        Lastly, the meta data db is kept in sync
        """
        source_folder = source_project["uuid"]
        dest_folder = destination_project["uuid"]

        # access layer
        async with self.engine.acquire() as conn, conn.begin():
            source_access_rights = await get_project_access_rights(
                conn, int(user_id), project_id=source_folder
            )
            dest_access_rights = await get_project_access_rights(
                conn, int(user_id), project_id=dest_folder
            )
        if not source_access_rights.read:
            logger.debug(
                "User %s was not allowed to read from project %s",
                user_id,
                source_folder,
            )
            raise web.HTTPForbidden(
                reason=f"User does not have enough access rights to read from project '{source_folder}'"
            )

        if not dest_access_rights.write:
            logger.debug(
                "User %s was not allowed to write to project %s",
                user_id,
                dest_folder,
            )
            raise web.HTTPForbidden(
                reason=f"User does not have enough access rights to write to project '{dest_folder}'"
            )

        # build up naming map based on labels
        uuid_name_dict = {}
        uuid_name_dict[dest_folder] = destination_project["name"]
        for src_node_id, src_node in source_project["workbench"].items():
            new_node_id = node_mapping.get(src_node_id)
            if new_node_id is not None:
                uuid_name_dict[new_node_id] = src_node["label"]

        async with self._create_aiobotocore_client_context() as aioboto_client:

            logger.debug(
                "Listing all items under  %s:%s/",
                self.simcore_bucket_name,
                source_folder,
            )

            # Step 1: List all objects for this project replace them with the destination object name
            # and do a copy at the same time collect some names
            # Note: the / at the end of the Prefix is VERY important, makes the listing several order of magnitudes faster
            response = await aioboto_client.list_objects_v2(
                Bucket=self.simcore_bucket_name, Prefix=f"{source_folder}/"
            )

            contents: List = response.get("Contents", [])
            logger.debug(
                "Listed  %s items under %s:%s/",
                len(contents),
                self.simcore_bucket_name,
                source_folder,
            )

            for item in contents:
                source_object_name = item["Key"]
                source_object_parts = Path(source_object_name).parts

                if len(source_object_parts) != 3:
                    # This may happen once we have shared/home folders
                    # FIXME: this might cause problems
                    logger.info(
                        "Skipping copy of '%s'. Expected three parts path!",
                        source_object_name,
                    )
                    continue

                old_node_id = source_object_parts[1]
                new_node_id = node_mapping.get(old_node_id)
                if new_node_id is not None:
                    old_filename = source_object_parts[2]
                    dest_object_name = str(
                        Path(dest_folder) / new_node_id / old_filename
                    )

                    copy_kwargs = dict(
                        CopySource={
                            "Bucket": self.simcore_bucket_name,
                            "Key": source_object_name,
                        },
                        Bucket=self.simcore_bucket_name,
                        Key=dest_object_name,
                    )
                    logger.debug("Copying %s ...", copy_kwargs)

                    # FIXME: if 5GB, it must use multipart upload Upload Part - Copy API
                    # SEE https://botocore.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.copy_object
                    await aioboto_client.copy_object(**copy_kwargs)

        # Step 2: List all references in outputs that point to datcore and copy over
        for node_id, node in destination_project["workbench"].items():
            outputs: Dict = node.get("outputs", {})
            for _, output in outputs.items():
                source = output["path"]

                if output.get("store") == DATCORE_ID:
                    destination_folder = str(Path(dest_folder) / node_id)
                    logger.info("Copying %s to %s", source, destination_folder)

                    destination = await self.copy_file_datcore_s3(
                        user_id=user_id,
                        dest_uuid=destination_folder,
                        source_uuid=source,
                        filename_missing=True,
                    )
                    assert destination.startswith(destination_folder)  # nosec

                    output["store"] = SIMCORE_S3_ID
                    output["path"] = destination

                elif output.get("store") == SIMCORE_S3_ID:
                    destination = str(Path(dest_folder) / node_id / Path(source).name)
                    output["store"] = SIMCORE_S3_ID
                    output["path"] = destination

        fmds = []
        async with self._create_aiobotocore_client_context() as aioboto_client:

            # step 3: list files first to create fmds
            # Note: the / at the end of the Prefix is VERY important, makes the listing several order of magnitudes faster
            response = await aioboto_client.list_objects_v2(
                Bucket=self.simcore_bucket_name, Prefix=f"{dest_folder}/"
            )

            if "Contents" in response:
                for item in response["Contents"]:
                    fmd = FileMetaData()
                    fmd.simcore_from_uuid(item["Key"], self.simcore_bucket_name)
                    fmd.project_name = uuid_name_dict.get(dest_folder, "Untitled")
                    fmd.node_name = uuid_name_dict.get(fmd.node_id, "Untitled")
                    fmd.raw_file_path = fmd.file_uuid
                    fmd.display_file_path = str(
                        Path(fmd.project_name) / fmd.node_name / fmd.file_name
                    )
                    fmd.user_id = user_id
                    fmd.file_size = item["Size"]
                    fmd.last_modified = str(item["LastModified"])
                    fmds.append(fmd)

        # step 4 sync db
        async with self.engine.acquire() as conn, conn.begin():
            # TODO: upsert in one statment of ALL
            for fmd in fmds:
                query = sa.select([file_meta_data]).where(
                    file_meta_data.c.file_uuid == fmd.file_uuid
                )
                # if file already exists, we might w
                rows = await conn.execute(query)
                exists = await rows.scalar()
                if exists:
                    delete_me = file_meta_data.delete().where(
                        file_meta_data.c.file_uuid == fmd.file_uuid
                    )
                    await conn.execute(delete_me)
                ins = file_meta_data.insert().values(**vars(fmd))
                await conn.execute(ins)

    # DELETE -------------------------------------

    async def delete_file(self, user_id: str, location: str, file_uuid: str):
        """Deletes a file given its fmd and location

        Additionally requires a user_id for 3rd party auth

        For internal storage, the db state should be updated upon completion via
        Notification mechanism

        For simcore.s3 we can use the file_name
        For datcore we need the full path
        """
        if location == SIMCORE_S3_STR:
            # FIXME: operation MUST be atomic, transaction??

            to_delete = []
            async with self.engine.acquire() as conn, conn.begin():
                can: Optional[AccessRights] = await get_file_access_rights(
                    conn, int(user_id), file_uuid
                )
                if not can.delete:
                    logger.debug(
                        "User %s was not allowed to delete file %s",
                        user_id,
                        file_uuid,
                    )
                    raise web.HTTPForbidden(
                        reason=f"User '{user_id}' does not have enough access rights to delete file {file_uuid}"
                    )

                query = sa.select(
                    [file_meta_data.c.bucket_name, file_meta_data.c.object_name]
                ).where(file_meta_data.c.file_uuid == file_uuid)

                async for row in conn.execute(query):
                    if self.s3_client.remove_objects(
                        row.bucket_name, [row.object_name]
                    ):
                        to_delete.append(file_uuid)

                await conn.execute(
                    file_meta_data.delete().where(
                        file_meta_data.c.file_uuid.in_(to_delete)
                    )
                )

        elif location == DATCORE_STR:
            # FIXME: review return inconsistencies
            api_token, api_secret = self._get_datcore_tokens(user_id)
            assert self.app  # nosec
            assert api_secret  # nosec
            assert api_token  # nosec
            await datcore_adapter.delete_file(
                self.app, api_token, api_secret, file_uuid
            )

    async def delete_project_simcore_s3(
        self, user_id: str, project_id: str, node_id: Optional[str] = None
    ) -> Optional[web.Response]:

        """Deletes all files from a given node in a project in simcore.s3 and updated db accordingly.
        If node_id is not given, then all the project files db entries are deleted.
        """

        # FIXME: operation MUST be atomic. Mark for deletion and remove from db when deletion fully confirmed

        async with self.engine.acquire() as conn, conn.begin():
            # access layer
            can: Optional[AccessRights] = await get_project_access_rights(
                conn, int(user_id), project_id
            )
            if not can.delete:
                logger.debug(
                    "User %s was not allowed to delete project %s",
                    user_id,
                    project_id,
                )
                raise web.HTTPForbidden(
                    reason=f"User does not have delete access for {project_id}"
                )

            delete_me = file_meta_data.delete().where(
                file_meta_data.c.project_id == project_id,
            )
            if node_id:
                delete_me = delete_me.where(file_meta_data.c.node_id == node_id)
            await conn.execute(delete_me)

        async with self._create_aiobotocore_client_context() as aioboto_client:
            # Note: the / at the end of the Prefix is VERY important, makes the listing several order of magnitudes faster
            response = await aioboto_client.list_objects_v2(
                Bucket=self.simcore_bucket_name,
                Prefix=f"{project_id}/{node_id}/" if node_id else f"{project_id}/",
            )

            objects_to_delete = []
            for f in response.get("Contents", []):
                objects_to_delete.append({"Key": f["Key"]})

            if objects_to_delete:
                response = await aioboto_client.delete_objects(
                    Bucket=self.simcore_bucket_name,
                    Delete={"Objects": objects_to_delete},
                )
                return response

    # SEARCH -------------------------------------

    async def search_files_starting_with(
        self, user_id: int, prefix: str
    ) -> List[FileMetaDataEx]:
        # Avoids using list_files since it accounts for projects/nodes
        # Storage should know NOTHING about those concepts
        files_meta = deque()

        async with self.engine.acquire() as conn, conn.begin():
            # access layer
            can_read_projects_ids = await get_readable_project_ids(conn, int(user_id))
            has_read_access = (
                file_meta_data.c.user_id == str(user_id)
            ) | file_meta_data.c.project_id.in_(can_read_projects_ids)

            stmt = sa.select([file_meta_data]).where(
                file_meta_data.c.file_uuid.startswith(prefix) & has_read_access
            )

            async for row in conn.execute(stmt):
                meta_extended = to_meta_data_extended(row)
                files_meta.append(meta_extended)

        return list(files_meta)

    async def create_soft_link(
        self, user_id: int, target_uuid: str, link_uuid: str
    ) -> FileMetaDataEx:

        # validate link_uuid
        async with self.engine.acquire() as conn:
            # TODO: select exists(select 1 from file_metadat where file_uuid=12)
            found = await conn.scalar(
                sa.select([file_meta_data.c.file_uuid]).where(
                    file_meta_data.c.file_uuid == link_uuid
                )
            )
            if found:
                raise ValueError(f"Invalid link {link_uuid}. Link already exists")

        # validate target_uuid
        target = await self.list_file(str(user_id), SIMCORE_S3_STR, target_uuid)
        if not target:
            raise ValueError(
                f"Invalid target '{target_uuid}'. File does not exists for this user"
            )

        # duplicate target and change the following columns:
        target.fmd.file_uuid = link_uuid
        target.fmd.file_id = link_uuid  # NOTE: api-server relies on this id
        target.fmd.is_soft_link = True

        async with self.engine.acquire() as conn:
            stmt = (
                file_meta_data.insert()
                .values(**attr.asdict(target.fmd))
                .returning(literal_column("*"))
            )

            result = await conn.execute(stmt)
            link = to_meta_data_extended(await result.first())
            return link

    async def synchronise_meta_data_table(
        self, location: str, dry_run: bool
    ) -> Dict[str, Any]:

        PRUNE_CHUNK_SIZE = 20

        removed: List[str] = []
        to_remove: List[str] = []

        async def _prune_db_table(conn):
            if not dry_run:
                await conn.execute(
                    file_meta_data.delete().where(
                        file_meta_data.c.object_name.in_(to_remove)
                    )
                )
            logger.info(
                "%s %s orphan items",
                "Would have deleted" if dry_run else "Deleted",
                len(to_remove),
            )
            removed.extend(to_remove)
            to_remove.clear()

        # ----------

        assert (  # nosec
            location == SIMCORE_S3_STR
        ), "Only with s3, no other sync implemented"  # nosec

        if location == SIMCORE_S3_STR:

            # NOTE: only valid for simcore, since datcore data is not in the database table
            # let's get all the files in the table
            logger.warning(
                "synchronisation of database/s3 storage started, this will take some time..."
            )

            async with self.engine.acquire() as conn, self._create_aiobotocore_client_context() as aioboto_client:

                number_of_rows_in_db = await conn.scalar(file_meta_data.count()) or 0
                logger.warning(
                    "Total number of entries to check %d",
                    number_of_rows_in_db,
                )

                assert isinstance(aioboto_client, AioBaseClient)  # nosec

                async for row in conn.execute(
                    sa.select([file_meta_data.c.object_name])
                ):
                    s3_key = row.object_name  # type: ignore

                    # now check if the file exists in S3
                    # SEE https://www.peterbe.com/plog/fastest-way-to-find-out-if-a-file-exists-in-s3
                    response = await aioboto_client.list_objects_v2(
                        Bucket=self.simcore_bucket_name, Prefix=s3_key
                    )
                    if response.get("KeyCount", 0) == 0:
                        # this file does not exist in S3
                        to_remove.append(s3_key)

                    if len(to_remove) >= PRUNE_CHUNK_SIZE:
                        await _prune_db_table(conn)

                if to_remove:
                    await _prune_db_table(conn)

                assert len(to_remove) == 0  # nosec
                assert len(removed) <= number_of_rows_in_db  # nosec

                logger.info(
                    "%s %d entries ",
                    "Would delete" if dry_run else "Deleting",
                    len(removed),
                )

        return {"removed": removed}
