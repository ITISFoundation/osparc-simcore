import asyncio
import os
import re
from operator import itemgetter
from typing import List, Tuple

import sqlalchemy as sa
from aiopg.sa import create_engine

from s3wrapper.s3_client import S3Client

from .datcore_wrapper import DatcoreWrapper

from .models import FileMetaData, file_meta_data

FileMetaDataVec = List[FileMetaData]

class Dsm:
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
    def __init__(self, db_endpoint: str, s3_client: S3Client):
        self.db_endpoint = db_endpoint
        self.s3_client = s3_client

    async def list_files(self, user_id: int, location: str, regex: str="", sortby: str="") -> FileMetaDataVec:
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
            dc = DatcoreWrapper(api_token, api_secret)
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

    async def delete_file(self, user_id: int, location: str, fmd: FileMetaData):
        """ Deletes a file given its fmd and location
        
            Additionally requires a user_id for 3rd party auth

            For internal storage, the db state should be updated upon completion via
            Notification mechanism

            For simcore.s3 we can use the file_id
            For datcore we need the full path
        """
        if location == "simcore.s3":
            file_id = fmd.file_id
            async with create_engine(self.db_endpoint) as engine:
                async with engine.acquire() as conn:
                    query = sa.select([file_meta_data]).where(file_meta_data.c.file_id == file_id)
                    async for row in conn.execute(query):
                        result_dict = dict(zip(row._result_proxy.keys, row._row))
                        d = FileMetaData(**result_dict)
                        # make sure this is the current user
                        if d.user_id == user_id:
                            # threaded please
                            if self.s3_client.remove_objects(d.bucket_name, [d.object_name]):
                                stmt = file_meta_data.delete().where(file_meta_data.c.file_id == file_id)
                                await conn.execute(stmt) 

        elif location == "datcore":
            api_token, api_secret = await self._get_datcore_tokens(user_id)
            dc = DatcoreWrapper(api_token, api_secret)
            return dc.delete_file(fmd)


    async def upload_file_to_datcore(self, user_id: int, local_file_path: str, remote_file_path: str, fmd: FileMetaData = None):
        # uploads a locally available file to dat core given the storage path, optionally attached some meta data
        tokens = await self._get_datcore_tokens(user_id)

        pass

    async def _get_datcore_tokens(self, user_id: int)->Tuple[str, str]:
        # actually we have to query the master db
        async with create_engine(self.db_endpoint) as engine:
            async with engine.acquire() as conn:
                query = sa.select([file_meta_data]).where(file_meta_data.c.user_id == user_id)
                _fmd = await conn.execute(query)
                api_token = os.environ.get("BF_API_KEY", "none")
                api_secret = os.environ.get("BF_API_SECRET", "none")
                return (api_token, api_secret)


    async def upload_link(self, fmd : FileMetaData):
         async with create_engine(self.db_endpoint) as engine:
            async with engine.acquire() as conn:
                ins = file_meta_data.insert().values(**vars(fmd))
                await conn.execute(ins)
                return self.s3_client.create_presigned_put_url(fmd.bucket_name, fmd.object_name)
        
    async def download_link(self, user_id: int, fmd: FileMetaData, location: str)->str:
        if location == "simcore.s3":
            return self.s3_client.create_presigned_get_url(fmd.bucket_name, fmd.object_name)

        elif location == "datcore":
            api_token, api_secret = await self._get_datcore_tokens(user_id)
            dc = DatcoreWrapper(api_token, api_secret)
            return dc.download_link(fmd)
