import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import aiobotocore
import attr
import sqlalchemy as sa
from aiobotocore.session import AioSession, ClientCreatorContext
from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.result import RowProxy
from servicelib.aiopg_utils import DBAPIError, PostgresRetryPolicyUponOperation
from servicelib.utils import fire_and_forget_task
from sqlalchemy.sql.expression import literal_column
from tenacity import retry

from .abc_storage import DataStorageInterface
from .access_layer import (
    AccessRights,
    get_file_access_rights,
    get_project_access_rights,
    get_readable_project_ids,
)
from .constants import SIMCORE_S3_ID, SIMCORE_S3_STR
from .models import (
    DatasetMetaData,
    FileMetaData,
    FileMetaDataEx,
    file_meta_data,
    get_location_from_id,
    projects,
)
from .s3wrapper.s3_client import MinioClientWrapper
from .utils import expo

logger = logging.getLogger(__name__)

postgres_service_retry_policy_kwargs = PostgresRetryPolicyUponOperation(logger).kwargs


def to_meta_data_extended(row: RowProxy) -> FileMetaDataEx:
    assert row
    meta = FileMetaData(**dict(row))  # type: ignore
    meta_extended = FileMetaDataEx(
        fmd=meta,
        parent_id=str(Path(meta.object_name).parent),
    )  # type: ignore
    return meta_extended


@dataclass
class S3DataStorage(DataStorageInterface):
    # TODO: perhaps can be used a cache? add a lifetime?

    s3_client: MinioClientWrapper
    engine: Engine
    simcore_bucket_name: str
    has_project_db: bool
    session: AioSession = attr.Factory(aiobotocore.get_session)
    app: Optional[web.Application] = None

    def _create_client_context(self) -> ClientCreatorContext:
        assert hasattr(self.session, "create_client")  #  nosec
        # pylint: disable=no-member
        return self.session.create_client(
            "s3",
            endpoint_url=self.s3_client.endpoint_url,
            aws_access_key_id=self.s3_client.access_key,
            aws_secret_access_key=self.s3_client.secret_key,
        )

    async def locations(self, user_id: str):
        return [{"name": SIMCORE_S3_STR, "id": SIMCORE_S3_ID}]

    @classmethod
    def location_from_id(cls, location_id: str):
        return get_location_from_id(location_id)

    # LIST/GET ---------------------------

    async def list_files(
        self,
        user_id: Union[str, int],
        uuid_filter: str = "",
        regex: str = "",
    ) -> List[FileMetaDataEx]:
        """Returns a list of file paths

        - Works for simcore.s3 and datcore
        - Can filter on uuid: useful to filter on project_id/node_id
        - Can filter upon regular expression (for now only on key: value pairs of the FileMetaData)
        """
        data = deque()

        accesible_projects_ids = []
        async with self.engine.acquire() as conn, conn.begin():
            accesible_projects_ids = await get_readable_project_ids(conn, int(user_id))
            has_read_access = (
                file_meta_data.c.user_id == str(user_id)
            ) | file_meta_data.c.project_id.in_(accesible_projects_ids)

            query = sa.select([file_meta_data]).where(has_read_access)

            async for row in conn.execute(query):
                d = FileMetaData(**dict(row))
                dex = FileMetaDataEx(fmd=d, parent_id=str(Path(d.object_name).parent))
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
                d.file_id = d.file_id
                if d.node_name and d.project_name:
                    d.display_file_path = str(
                        Path(d.project_name) / Path(d.node_name) / Path(d.file_name)
                    )
                    # once the data was sync to postgres metadata table at this point
                    clean_data.append(dx)

            data = clean_data

        if uuid_filter:
            # TODO: incorporate this in db query!
            _query = re.compile(uuid_filter, re.IGNORECASE)
            filtered_data = deque()
            for dx in data:
                d = dx.fmd
                if _query.search(d.file_id):
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

    async def get_dataset(
        self, user_id: str, dataset_id: str
    ) -> Union[List[FileMetaData], List[FileMetaDataEx]]:
        # this is a cheap shot, needs fixing once storage/db is in sync
        data = []

        data: List[FileMetaDataEx] = await self.list_files(
            user_id, location, uuid_filter=dataset_id + "/"
        )
        return data

    async def list_datasets(self, user_id: str) -> List[DatasetMetaData]:
        """Returns a list of top level datasets

        Works for simcore.s3 and datcore

        """
        data = []

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

        return data

    async def list_file(self, user_id: str, file_id: str) -> Optional[FileMetaDataEx]:

        async with self.engine.acquire() as conn, conn.begin():
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if can.read:
                query = sa.select([file_meta_data]).where(
                    file_meta_data.c.file_id == file_id
                )
                result = await conn.execute(query)
                row = await result.first()
                return to_meta_data_extended(row) if row else None
            # FIXME: returns None in both cases: file does not exist or use has no access
            logger.debug("User %s cannot read file %s", user_id, file_id)
            return None

    # UPLOAD/DOWNLOAD LINKS ---------------------------

    async def _metadata_file_updater(
        self,
        file_id: str,
        bucket_name: str,
        object_name: str,
        file_size: int,
        last_modified: str,
        max_update_retries: int = 50,
    ):
        """
        Will retry max_update_retries to update the metadata on the file after an upload.
        If it is not successfull it will exit and log an error.

        Note: MinIO bucket notifications are not available with S3, that's why we have the
        following hacky solution
        """
        current_iteraction = 0

        async with self._create_client_context() as client:
            current_iteraction += 1
            continue_loop = True
            sleep_generator = expo()
            update_succeeded = False

            while continue_loop:
                result = await client.list_objects_v2(
                    Bucket=bucket_name, Prefix=object_name
                )
                sleep_amount = next(sleep_generator)
                continue_loop = current_iteraction <= max_update_retries

                if "Contents" not in result:
                    logger.info("File '%s' was not found in the bucket", object_name)
                    await asyncio.sleep(sleep_amount)
                    continue

                new_file_size = result["Contents"][0]["Size"]
                new_last_modified = str(result["Contents"][0]["LastModified"])
                if file_size == new_file_size or last_modified == new_last_modified:
                    logger.info("File '%s' did not change yet", object_name)
                    await asyncio.sleep(sleep_amount)
                    continue

                file_e_tag = result["Contents"][0]["ETag"].strip('"')
                # finally update the data in the database and exit
                continue_loop = False

                logger.info(
                    "Obtained this from S3: new_file_size=%s new_last_modified=%s file ETag=%s",
                    new_file_size,
                    new_last_modified,
                    file_e_tag,
                )

                async with self.engine.acquire() as conn:
                    query = (
                        file_meta_data.update()
                        .where(file_meta_data.c.file_id == file_id)
                        .values(
                            file_size=new_file_size,
                            last_modified=new_last_modified,
                            entity_tag=file_e_tag,
                        )
                    )  # primary key search is faster
                    await conn.execute(query)
                    update_succeeded = True
            if not update_succeeded:
                logger.error("Could not update file metadata for '%s'", file_id)

    async def upload_link(self, user_id: str, file_id: str):
        """
        Creates pre-signed upload link and updates metadata table when
        link is used and upload is successfuly completed

        SEE _metadata_file_updater
        """

        async with self.engine.acquire() as conn:
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.write:
                logger.debug(
                    "User %s was not allowed to upload file %s", user_id, file_id
                )
                raise web.HTTPForbidden(
                    reason=f"User does not have enough access rights to upload file {file_id}"
                )

        @retry(**postgres_service_retry_policy_kwargs)
        async def _init_metadata() -> Tuple[int, str]:
            async with self.engine.acquire() as conn:
                fmd = FileMetaData()
                fmd.simcore_from_uuid(file_id, self.simcore_bucket_name)
                fmd.user_id = user_id  # NOTE: takes ownership of uploaded data

                query = sa.select([file_meta_data]).where(
                    file_meta_data.c.file_id == file_id
                )
                # if file already exists, we might want to update a time-stamp
                exists = await (await conn.execute(query)).scalar()
                if exists is None:
                    ins = file_meta_data.insert().values(**vars(fmd))
                    await conn.execute(ins)
                return fmd.file_size, fmd.last_modified

        file_size, last_modified = await _init_metadata()

        bucket_name = self.simcore_bucket_name
        object_name = file_id

        # a parallel task is tarted which will update the metadata of the updated file
        # once the update has finished.
        fire_and_forget_task(
            self._metadata_file_updater(
                file_id=file_id,
                bucket_name=bucket_name,
                object_name=object_name,
                file_size=file_size,
                last_modified=last_modified,
            )
        )
        return self.s3_client.create_presigned_put_url(bucket_name, object_name)

    async def download_link_s3(self, file_id: str, user_id: int) -> str:

        # access layer
        async with self.engine.acquire() as conn:
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.read:
                # NOTE: this is tricky. A user with read access can download and data!
                # If write permission would be required, then shared projects as views cannot
                # recover data in nodes (e.g. jupyter cannot pull work data)
                #
                logger.debug(
                    "User %s was not allowed to download file %s", user_id, file_id
                )
                raise web.HTTPForbidden(
                    reason=f"User does not have enough rights to download {file_id}"
                )

        bucket_name = self.simcore_bucket_name
        async with self.engine.acquire() as conn:
            stmt = sa.select([file_meta_data.c.object_name]).where(
                file_meta_data.c.file_id == file_id
            )
            object_name: str = await conn.scalar(stmt)

            if object_name is None:
                raise web.HTTPNotFound(
                    reason=f"File '{file_id}' does not exists in storage."
                )

        link = self.s3_client.create_presigned_get_url(bucket_name, object_name)
        return link

    # COPY -----------------------------

    async def copy_file(self, user_id: str, dest_uuid: str, source_uuid: str):
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

    # DELETE -------------------------------------

    async def delete_file(self, user_id: str, file_id: str):
        """Deletes a file given its fmd and location

        Additionally requires a user_id for 3rd party auth

        For internal storage, the db state should be updated upon completion via
        Notification mechanism

        For simcore.s3 we can use the file_name
        For datcore we need the full path
        """
        # FIXME: operation MUST be atomic, transaction??

        to_delete = []
        async with self.engine.acquire() as conn, conn.begin():
            can: Optional[AccessRights] = await get_file_access_rights(
                conn, int(user_id), file_id
            )
            if not can.delete:
                logger.debug(
                    "User %s was not allowed to delete file %s",
                    user_id,
                    file_id,
                )
                raise web.HTTPForbidden(
                    reason=f"User '{user_id}' does not have enough access rights to delete file {file_id}"
                )

            query = sa.select(
                [file_meta_data.c.bucket_name, file_meta_data.c.object_name]
            ).where(file_meta_data.c.file_id == file_id)

            async for row in conn.execute(query):
                if self.s3_client.remove_objects(row.bucket_name, [row.object_name]):
                    to_delete.append(file_id)

            await conn.execute(
                file_meta_data.delete().where(file_meta_data.c.file_id.in_(to_delete))
            )

    async def delete_project(
        self, user_id: str, project_id: str, node_id: Optional[str] = None
    ) -> web.Response:

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

        async with self._create_client_context() as client:
            # Note: the / at the end of the Prefix is VERY important, makes the listing several order of magnitudes faster
            response = await client.list_objects_v2(
                Bucket=self.simcore_bucket_name,
                Prefix=f"{project_id}/{node_id}/" if node_id else f"{project_id}/",
            )

            objects_to_delete = []
            for f in response.get("Contents", []):
                objects_to_delete.append({"Key": f["Key"]})

            if objects_to_delete:
                response = await client.delete_objects(
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
                file_meta_data.c.file_id.startswith(prefix) & has_read_access
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
            # TODO: select exists(select 1 from file_metadat where file_id=12)
            found = await conn.scalar(
                sa.select([file_meta_data.c.file_id]).where(
                    file_meta_data.c.file_id == link_uuid
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
        target.fmd.file_id = link_uuid
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
