import asyncio
import logging
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from operator import itemgetter
from pathlib import Path
from typing import Dict, List, Tuple

import aiobotocore
import aiofiles
import aiohttp
import attr
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa import Engine
from sqlalchemy.sql import and_
from yarl import URL

from s3wrapper.s3_client import S3Client
from servicelib.aiopg_utils import DBAPIError

from .datcore_wrapper import DatcoreWrapper
from .models import (FileMetaData, _location_from_id, _parse_datcore,
                     file_meta_data, projects, user_to_projects)
from .s3 import get_config_s3
from .settings import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY, APP_DSM_KEY,
                       APP_S3_KEY, DATCORE_ID, DATCORE_STR, SIMCORE_S3_ID,
                       SIMCORE_S3_STR)

#pylint: disable=W0212
#FIXME: W0212:Access to a protected member _result_proxy of a client class

#pylint: disable=E1120
##FIXME: E1120:No value for argument 'dml' in method call

logger = logging.getLogger(__name__)


FileMetaDataVec = List[FileMetaData]

async def _setup_dsm(app: web.Application):
    cfg = app[APP_CONFIG_KEY]
    main_cfg = cfg["main"]

    main_cfg = cfg["main"]

    engine = app.get(APP_DB_ENGINE_KEY)
    loop = asyncio.get_event_loop()
    s3_client = app.get(APP_S3_KEY)

    max_workers = main_cfg["max_workers"]
    pool = ThreadPoolExecutor(max_workers=max_workers)

    s3_cfg = get_config_s3(app)
    bucket_name = s3_cfg["bucket_name"]

    dsm = DataStorageManager(s3_client, engine, loop, pool, bucket_name)

    app[APP_DSM_KEY] = dsm

    yield
    #clean up

def setup_dsm(app: web.Application):
    app.cleanup_ctx.append(_setup_dsm)

@attr.s(auto_attribs=True)
class DatCoreApiToken:
    api_token: str = None
    api_secret: str = None

    def to_tuple(self):
        return (self.api_token, self.api_secret)



@attr.s(auto_attribs=True)
class DataStorageManager:
    """ Data storage manager

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
    s3_client: S3Client
    engine: Engine
    loop: object
    pool: ThreadPoolExecutor
    simcore_bucket_name: str
    datcore_tokens: Dict[str, DatCoreApiToken]=attr.Factory(dict)
    # TODO: perhaps can be used a cache? add a lifetime?


    def _get_datcore_tokens(self, user_id: str)->Tuple[str, str]:
        token = self.datcore_tokens.get(user_id, DatCoreApiToken()) # pylint: disable=E1101
        return token.to_tuple()

    async def locations(self, user_id: str):
        locs = []
        simcore_s3 = {
            "name" : SIMCORE_S3_STR,
            "id" : SIMCORE_S3_ID
        }
        locs.append(simcore_s3)

        ping_ok = await self.ping_datcore(user_id=user_id)
        if ping_ok:
            datcore = {
                "name" : DATCORE_STR,
                "id"   : DATCORE_ID
            }
            locs.append(datcore)

        return locs

    @classmethod
    def location_from_id(cls, location_id : str):
        return _location_from_id(location_id)

    async def ping_datcore(self, user_id: str) -> bool:
        """ Checks whether user account in datcore is accesible

        :param user_id: user identifier
        :type user_id: str
        :return: True if user can access his datcore account
        :rtype: bool
        """

        api_token, api_secret = self._get_datcore_tokens(user_id)
        logger.info("token: %s, secret %s", api_token, api_secret)
        if api_token:
            dcw = DatcoreWrapper(api_token, api_secret, self.loop, self.pool)
            profile = await dcw.ping()
            if profile:
                return True
        return False

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    async def list_files(self, user_id: str, location: str, uuid_filter: str ="", regex: str="", sortby: str="") -> FileMetaDataVec:
        """ Returns a list of file paths

            Works for simcore.s3 and datcore

            Can filter on uuid: useful to filter on project_id/node_id

            Can filter upon regular expression (for now only on key: value pairs of the FileMetaData)

            Can sort results by key [assumes that sortby is actually a key in the FileMetaData]

            order is: sort by key, filter by uuid or regex
        """
        data = []
        if location == SIMCORE_S3_STR:
            async with self.engine.acquire() as conn:
                query = sa.select([file_meta_data]).where(file_meta_data.c.user_id == user_id)
                async for row in conn.execute(query):
                    result_dict = dict(zip(row._result_proxy.keys, row._row))
                    d = FileMetaData(**result_dict)
                    data.append(d)

            uuid_name_dict = {}
            # now parse the project to search for node/project names
            try:
                async with self.engine.acquire() as conn:
                    joint_table = user_to_projects.join(projects)
                    query = sa.select([projects]).select_from(joint_table)\
                        .where(user_to_projects.c.user_id == user_id)

                    async for row in conn.execute(query):
                        proj_data = {key:value for key,value in row.items()}

                        uuid_name_dict[proj_data["uuid"]] = proj_data["name"]
                        wb = proj_data['workbench']
                        for node in wb.keys():
                            uuid_name_dict[node] = wb[node]['label']
            except DBAPIError as _err:
                logger.exception("Error querying database for project names")

            if uuid_name_dict:
                # only keep files from non-deleted project --> This needs to be fixed
                clean_data = []
                for d in data:
                    if d.project_id in uuid_name_dict:
                        d.project_name = uuid_name_dict[d.project_id]
                        if d.node_id in uuid_name_dict:
                            d.node_name = uuid_name_dict[d.node_id]

                        d.raw_file_path = str(Path(d.project_id) / Path(d.node_id) / Path(d.file_name))
                        d.display_file_path = d.raw_file_path
                        if d.node_name and d.project_name:
                            d.display_file_path = str(Path(d.project_name) / Path(d.node_name) / Path(d.file_name))
                        async with self.engine.acquire() as conn:
                            query = file_meta_data.update().\
                            where(and_(file_meta_data.c.node_id==d.node_id,
                                    file_meta_data.c.user_id==d.user_id)).\
                            values(project_name=d.project_name,
                                    node_name = d.node_name,
                                    raw_file_path=d.raw_file_path,
                                    display_file_path=d.display_file_path)
                            await conn.execute(query)
                            clean_data.append(d)

                data = clean_data
                for d in data:
                    logger.info(d)

                # same as above, make sure file is physically present on s3
                clean_data = []
                # MaG: This is inefficient: Do this automatically when file is modified
                _loop = asyncio.get_event_loop()
                session = aiobotocore.get_session(loop=_loop)
                async with session.create_client('s3', endpoint_url="http://"+self.s3_client.endpoint, aws_access_key_id=self.s3_client.access_key,
                     aws_secret_access_key=self.s3_client.secret_key) as client:
                    responses = await asyncio.gather(*[client.list_objects_v2(Bucket=d.bucket_name, Prefix=_d) for _d in [__d.object_name for __d in data]])
                    for d, resp in zip(data, responses):
                        if 'Contents' in resp:
                            clean_data.append(d)
                            d.file_size = resp['Contents'][0]['Size']
                            d.last_modified = str(resp['Contents'][0]['LastModified'])
                            async with self.engine.acquire() as conn:
                                query = file_meta_data.update().\
                                where(and_(file_meta_data.c.node_id==d.node_id,
                                        file_meta_data.c.user_id==d.user_id)).\
                                values(file_size=d.file_size,
                                        last_modified=d.last_modified)
                                await conn.execute(query)
                data = clean_data

        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            dcw = DatcoreWrapper(api_token, api_secret, self.loop, self.pool)
            data = await dcw.list_files_recursively()

        if sortby:
            data = sorted(data, key=itemgetter(sortby))


        if uuid_filter:
            _query = re.compile(uuid_filter, re.IGNORECASE)
            filtered_data = []
            for d in data:
                if _query.search(d.file_uuid):
                    filtered_data.append(d)

            return filtered_data

        if regex:
            _query = re.compile(regex, re.IGNORECASE)
            filtered_data = []
            for d in data:
                _vars = vars(d)
                for v in _vars.keys():
                    if _query.search(v) or _query.search(str(_vars[v])):
                        filtered_data.append(d)
                        break
            return filtered_data

        return data

    async def list_file(self, user_id: str, location: str, file_uuid: str) -> FileMetaData:
        if location == SIMCORE_S3_STR:
            # TODO: get engine from outside
            async with self.engine.acquire() as conn:
                query = sa.select([file_meta_data]).where(and_(file_meta_data.c.user_id == user_id,
                file_meta_data.c.file_uuid == file_uuid))
                async for row in conn.execute(query):
                    result_dict = dict(zip(row._result_proxy.keys, row._row))
                    d = FileMetaData(**result_dict)
                    return d
        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            _dcw = DatcoreWrapper(api_token, api_secret, self.loop, self.pool)
            data = [] #await _dcw.list_file(file_uuid)
            return data

    async def delete_file(self, user_id: str, location: str, file_uuid: str):
        """ Deletes a file given its fmd and location

            Additionally requires a user_id for 3rd party auth

            For internal storage, the db state should be updated upon completion via
            Notification mechanism

            For simcore.s3 we can use the file_name
            For datcore we need the full path
        """
        if location == SIMCORE_S3_STR:
            async with self.engine.acquire() as conn:
                query = sa.select([file_meta_data]).where(file_meta_data.c.file_uuid == file_uuid)
                async for row in conn.execute(query):
                    result_dict = dict(zip(row._result_proxy.keys, row._row))
                    d = FileMetaData(**result_dict)
                    # make sure this is the current user
                    if d.user_id == user_id:
                        if self.s3_client.remove_objects(d.bucket_name, [d.object_name]):
                            stmt = file_meta_data.delete().where(file_meta_data.c.file_uuid == file_uuid)
                            await conn.execute(stmt)

        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            dcw = DatcoreWrapper(api_token, api_secret, self.loop, self.pool)
            destination, filename = _parse_datcore(file_uuid)
            return await dcw.delete_file(destination, filename)

    async def upload_file_to_datcore(self, user_id: str, local_file_path: str, destination: str, fmd: FileMetaData = None): # pylint: disable=W0613
        # uploads a locally available file to dat core given the storage path, optionally attached some meta data
        api_token, api_secret = self._get_datcore_tokens(user_id)
        dcw = DatcoreWrapper(api_token, api_secret, self.loop, self.pool)
        await dcw.upload_file(destination, local_file_path, fmd)

        # actually we have to query the master db
    async def upload_link(self, user_id: str, file_uuid: str):
        async with self.engine.acquire() as conn:
            fmd = FileMetaData()
            fmd.simcore_from_uuid(file_uuid, self.simcore_bucket_name)
            fmd.user_id = user_id
            query = sa.select([file_meta_data]).where(file_meta_data.c.file_uuid == file_uuid)
            # if file already exists, we might want to update a time-stamp
            rows = await conn.execute(query)
            exists = await rows.scalar()
            if exists is None:
                ins = file_meta_data.insert().values(**vars(fmd))
                await conn.execute(ins)
            bucket_name = self.simcore_bucket_name
            object_name = file_uuid
            return self.s3_client.create_presigned_put_url(bucket_name, object_name)

    async def copy_file(self, user_id: str, dest_location: str, dest_uuid: str, source_location: str, source_uuid: str):
        if source_location == SIMCORE_S3_STR:
            if dest_location == DATCORE_STR:
                # source is s3, get link and copy to datcore
                bucket_name = self.simcore_bucket_name
                object_name = source_uuid
                destination, filename = _parse_datcore(dest_uuid)
                tmp_dirpath = tempfile.mkdtemp()
                local_file_path = os.path.join(tmp_dirpath, filename)
                url = self.s3_client.create_presigned_get_url(bucket_name, object_name)
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            f = await aiofiles.open(local_file_path, mode='wb')
                            await f.write(await resp.read())
                            await f.close()
                            # and then upload
                            await self.upload_file_to_datcore(user_id=user_id, local_file_path=local_file_path,
                                destination=destination)
                shutil.rmtree(tmp_dirpath)
            elif dest_location == SIMCORE_S3_STR:
                # source is s3, location is s3
                to_bucket_name = self.simcore_bucket_name
                to_object_name = dest_uuid
                from_bucket = self.simcore_bucket_name
                from_object_name = source_uuid
                from_bucket_object_name = os.path.join(from_bucket, from_object_name)
                # FIXME: This is not async!
                self.s3_client.copy_object(to_bucket_name, to_object_name, from_bucket_object_name)
                # update db
                async with self.engine.acquire() as conn:
                    fmd = FileMetaData()
                    fmd.simcore_from_uuid(dest_uuid, self.simcore_bucket_name)
                    fmd.user_id = user_id
                    ins = file_meta_data.insert().values(**vars(fmd))
                    await conn.execute(ins)
        elif source_location == DATCORE_STR:
            if dest_location == DATCORE_STR:
                raise NotImplementedError("copy files from datcore 2 datcore not impl")
            if dest_location == SIMCORE_S3_STR:
                # 2 steps: Get download link for local copy, the upload link to s3
                # TODO: This should be a redirect stream!
                dc_link = await self.download_link(user_id=user_id, location=source_location, file_uuid=source_uuid)
                s3_upload_link = await self.upload_link(user_id, dest_uuid)
                filename = source_uuid.split("/")[-1]
                tmp_dirpath = tempfile.mkdtemp()
                local_file_path = os.path.join(tmp_dirpath,filename)
                async with aiohttp.ClientSession() as session:
                    async with session.get(dc_link) as resp:
                        if resp.status == 200:
                            f = await aiofiles.open(local_file_path, mode='wb')
                            await f.write(await resp.read())
                            await f.close()
                            s3_upload_link = URL(s3_upload_link)
                            async with session.put(s3_upload_link, data=Path(local_file_path).open('rb')) as resp:
                                if resp.status > 299:
                                    _response_text = await resp.text()

    async def download_link(self, user_id: str, location: str, file_uuid: str)->str:
        link = None
        if location == SIMCORE_S3_STR:
            bucket_name = self.simcore_bucket_name
            object_name = file_uuid
            link = self.s3_client.create_presigned_get_url(bucket_name, object_name)
        elif location == DATCORE_STR:
            api_token, api_secret = self._get_datcore_tokens(user_id)
            dcw = DatcoreWrapper(api_token, api_secret, self.loop, self.pool)
            destination, filename = _parse_datcore(file_uuid)
            link = await dcw.download_link(destination, filename)
        return link
