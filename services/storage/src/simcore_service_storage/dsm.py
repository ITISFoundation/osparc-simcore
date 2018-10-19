import os
import re
import shutil
import tempfile
from operator import itemgetter
from pathlib import Path
from typing import List, Tuple

import aiofiles
import aiohttp
import attr
import sqlalchemy as sa
from aiopg.sa import create_engine
from sqlalchemy.sql import and_

from s3wrapper.s3_client import S3Client

from .datcore_wrapper import DatcoreWrapper
from .models import (FileMetaData, _location_from_id, _locations,
                     _parse_datcore, _parse_simcore, file_meta_data)

#pylint: disable=W0212
#FIXME: W0212:Access to a protected member _result_proxy of a client class

#pylint: disable=E1120
##FIXME: E1120:No value for argument 'dml' in method call


FileMetaDataVec = List[FileMetaData]



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
    db_endpoint: str
    s3_client: S3Client
    python27_exec: Path

    def locations(self):
        return _locations()

    def location_from_id(self, location_id : str):
        return _location_from_id(location_id)

    async def list_files(self, user_id: str, location: str, regex: str="", sortby: str="") -> FileMetaDataVec:
        """ Returns a list of file paths

            Works for simcore.s3 and datcore

            Can filter upon regular expression (for now only on key: value pairs of the FileMetaData)

            Can sort results by key [assumes that sortby is actually a key in the FileMetaData]
        """
        data = []
        if location == "simcore.s3":
            async with create_engine(self.db_endpoint) as engine:
                async with engine.acquire() as conn:
                    query = sa.select([file_meta_data]).where(file_meta_data.c.user_id == user_id)
                    async for row in conn.execute(query):
                        result_dict = dict(zip(row._result_proxy.keys, row._row))
                        d = FileMetaData(**result_dict)
                        data.append(d)
        elif location == "datcore":
            api_token, api_secret = await self._get_datcore_tokens(user_id)
            dc = DatcoreWrapper(api_token, api_secret, self.python27_exec)
            return dc.list_files(regex, sortby)

        if sortby:
            data = sorted(data, key=itemgetter(sortby))

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
        if location == "simcore.s3":
            async with create_engine(self.db_endpoint) as engine:
                async with engine.acquire() as conn:
                    query = sa.select([file_meta_data]).where(and_(file_meta_data.c.user_id == user_id,
                    file_meta_data.c.file_uuid == file_uuid))
                    async for row in conn.execute(query):
                        result_dict = dict(zip(row._result_proxy.keys, row._row))
                        d = FileMetaData(**result_dict)
                        return d
        elif location == "datcore":
            api_token, api_secret = await self._get_datcore_tokens(user_id)
            dc = DatcoreWrapper(api_token, api_secret, self.python27_exec)
            raise NotImplementedError


    async def delete_file(self, user_id: str, location: str, file_uuid: str):
        """ Deletes a file given its fmd and location

            Additionally requires a user_id for 3rd party auth

            For internal storage, the db state should be updated upon completion via
            Notification mechanism

            For simcore.s3 we can use the file_id
            For datcore we need the full path
        """
        if location == "simcore.s3":
            async with create_engine(self.db_endpoint) as engine:
                async with engine.acquire() as conn:
                    query = sa.select([file_meta_data]).where(file_meta_data.c.file_uuid == file_uuid)
                    async for row in conn.execute(query):
                        result_dict = dict(zip(row._result_proxy.keys, row._row))
                        d = FileMetaData(**result_dict)
                        # make sure this is the current user
                        if d.user_id == user_id:
                            if self.s3_client.remove_objects(d.bucket_name, [d.object_name]):
                                stmt = file_meta_data.delete().where(file_meta_data.c.file_uuid == file_uuid)
                                await conn.execute(stmt)

        elif location == "datcore":
            api_token, api_secret = await self._get_datcore_tokens(user_id)
            dc = DatcoreWrapper(api_token, api_secret, self.python27_exec)
            dataset, filename = _parse_datcore(file_uuid)
            return dc.delete_file(dataset=dataset, filename=filename)

    async def upload_file_to_datcore(self, user_id: str, local_file_path: str, datcore_bucket: str, fmd: FileMetaData = None): # pylint: disable=W0613
        # uploads a locally available file to dat core given the storage path, optionally attached some meta data
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        dc = DatcoreWrapper(api_token, api_secret, self.python27_exec)
        await dc.upload_file_async(datcore_bucket, local_file_path, fmd)

    async def _get_datcore_tokens(self, user_id: str)->Tuple[str, str]:
        # actually we have to query the master db
        async with create_engine(self.db_endpoint) as engine:
            # FIXME: load from app[APP_DB_ENGINE_KEY]
            async with engine.acquire() as conn:
                query = sa.select([file_meta_data]).where(file_meta_data.c.user_id == user_id)
                _fmd = await conn.execute(query)
                # FIXME: load from app[APP_CONFIG_KEY]["test_datcore"]
                api_token = os.environ.get("BF_API_KEY", "none")
                api_secret = os.environ.get("BF_API_SECRET", "none")
                return (api_token, api_secret)


    async def upload_link(self, user_id: str, file_uuid: str):
        async with create_engine(self.db_endpoint) as engine:
            async with engine.acquire() as conn:
                fmd = FileMetaData()
                fmd.simcore_from_uuid(file_uuid)
                fmd.user_id = user_id
                ins = file_meta_data.insert().values(**vars(fmd))
                await conn.execute(ins)
                bucket_name, object_name = _parse_simcore(file_uuid)
                return self.s3_client.create_presigned_put_url(bucket_name, object_name)

    async def copy_file(self, user_id: str, location: str, file_uuid: str, source_uuid: str):
        if location == "datcore":
            # source is s3, get link
            bucket_name, object_name = _parse_simcore(source_uuid)
            datcore_bucket, file_path = _parse_datcore(file_uuid)
            filename = file_path.split("/")[-1]
            tmp_dirpath = tempfile.mkdtemp()
            local_file_path = os.path.join(tmp_dirpath,filename)
            url = self.s3_client.create_presigned_get_url(bucket_name, object_name)
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        f = await aiofiles.open(local_file_path, mode='wb')
                        await f.write(await resp.read())
                        await f.close()
                        # and then upload
                        await self.upload_file_to_datcore(user_id=user_id, local_file_path=local_file_path,
                            datcore_bucket=datcore_bucket)

            shutil.rmtree(tmp_dirpath)

    async def download_link(self, user_id: str, location: str, file_uuid: str)->str:
        link = None
        if location == "simcore.s3":
            bucket_name, object_name = _parse_simcore(file_uuid)
            link = self.s3_client.create_presigned_get_url(bucket_name, object_name)
        elif location == "datcore":
            api_token, api_secret = await self._get_datcore_tokens(user_id)
            dc = DatcoreWrapper(api_token, api_secret, self.python27_exec)
            dataset, filename = _parse_datcore(file_uuid)
            link = dc.download_link(dataset=dataset, filename=filename)
        return link
