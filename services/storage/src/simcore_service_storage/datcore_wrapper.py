import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path
from typing import List

import attr

from .datcore import DatcoreClient
from .models import FileMetaData
from .settings import DATCORE_ID, DATCORE_STR

FileMetaDataVec = List[FileMetaData]

CURRENT_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

#FIXME: W0703: Catching too general exception Exception (broad-except)
# pylint: disable=W0703


#TODO: Use async callbacks for retreival of progress and pass via rabbit to server
def make_async(func):
    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        blocking_task = self.loop.run_in_executor(self.pool, func, self, *args, **kwargs)
        _completed, _pending = await asyncio.wait([blocking_task])
        results = [t.result() for t in _completed]
        # TODO: does this always work?
        return results[0]
    return async_wrapper

class DatcoreWrapper:
    """ Wrapper to call the python2 api from datcore

        This can go away now. Next cleanup round...

    """
    # pylint: disable=R0913
    # Too many arguments
    def __init__(self, api_token: str, api_secret: str, loop: object, pool: ThreadPoolExecutor):
        self.api_token = api_token
        self.api_secret = api_secret

        self.loop = loop
        self.pool = pool

        self.d_client =  DatcoreClient(api_token=api_token, api_secret=api_secret,
                host='https://api.blackfynn.io')

    @make_async
    def list_files(self, regex = "", sortby = "")->FileMetaDataVec: #pylint: disable=W0613
        try:
            files = self.d_client.list_files()
        except Exception as e:
            logger.exception("Error listing datcore files %s", e)

        data = []
        for f in files:
            # extract bucket name, object name and filename
            parts = f.strip("/").split("/")
            file_name = parts[-1]
            if len(parts) > 1:
                bucket_name = parts[0]
                object_name = "/".join(parts[1:])
            else:
                bucket_name = ""
                object_name = file_name

            file_uuid = os.path.join(bucket_name, object_name)
            # at the moment, no metadata there
            fmd = FileMetaData(bucket_name=bucket_name, file_name=file_name, object_name=object_name,
             location=DATCORE_STR, location_id=DATCORE_ID, file_uuid=file_uuid)
            data.append(fmd)

        return data

    @make_async
    def list_files_recursively(self, regex = "", sortby = "")->FileMetaDataVec: #pylint: disable=W0613
        files = []
        try:
            files = self.d_client.list_files_recursively()
        except Exception as e:
            logger.exception("Error listing datcore files %s", e)

        return files

    @make_async
    def delete_file(self, dataset: str, filename: str):
        # the object can be found in dataset/filename <-> bucket_name/object_name
        try:
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_file(ds, filename)
        except Exception as e:
            logger.exception("Error deleting datcore file %s", e)

    @make_async
    def download_link(self, dataset: str, filename: str):
        url = ""
        try:
            ds = self.d_client.get_dataset(dataset)
            url = ""
            if ds is not None:
                url = self.d_client.download_link(ds, filename)
        except Exception as e:
            logger.exception("Error getting datcore download link %s", e)

        return url


    @make_async
    def create_test_dataset(self, dataset):
        try:
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_files(ds)
            else:
                self.d_client.create_dataset(dataset)
        except Exception as e:
            logger.exception("Error creating test dataset %s", e)


    @make_async
    def delete_test_dataset(self, dataset):
        try:
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_files(ds)
        except Exception as e:
            logger.exception("Error deleting test dataset %s", e)

    @make_async
    def upload_file(self, dataset: str, local_path: str, meta_data: FileMetaData = None):
        json_meta = ""
        if meta_data:
            json_meta = json.dumps(attr.asdict(meta_data))
        try:
            ds = self.d_client.get_dataset(dataset)
            str_meta = json_meta
            if str_meta :
                meta_data = json.loads(str_meta)
                self.d_client.upload_file(ds, local_path, meta_data)
            else:
                self.d_client.upload_file(ds, local_path)
            return True
        except Exception as e:
            logger.exception("Error uploading file to datcore %s", e)
            return False

    @make_async
    def ping(self):
        try:
            profile = self.d_client.profile()
            ok = profile is not None
            return ok
        except Exception as e:
            logger.exception("Error pinging %s", e)
            return False
