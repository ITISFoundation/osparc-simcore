import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path
from typing import List

import attr

from .datcore import DatcoreClient
from .models import FileMetaData, FileMetaDataEx

FileMetaDataVec = List[FileMetaData]
FileMetaDataExVec = List[FileMetaDataEx]

CURRENT_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

# FIXME: W0703: Catching too general exception Exception (broad-except)
# pylint: disable=W0703


# TODO: Use async callbacks for retreival of progress and pass via rabbit to server
def make_async(func):
    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        blocking_task = self.loop.run_in_executor(
            self.pool, func, self, *args, **kwargs
        )
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
    def __init__(
        self, api_token: str, api_secret: str, loop: object, pool: ThreadPoolExecutor
    ):
        self.api_token = api_token
        self.api_secret = api_secret

        self.loop = loop
        self.pool = pool

        self.d_client = DatcoreClient(
            api_token=api_token, api_secret=api_secret, host="https://api.blackfynn.io"
        )

    @make_async
    def list_files_recursively(self) -> FileMetaDataVec:  # pylint: disable=W0613
        files = []
        try:
            files = self.d_client.list_files_recursively()
        except Exception:
            logger.exception("Error listing datcore files")

        return files

    @make_async
    def list_files_raw(self) -> FileMetaDataExVec:  # pylint: disable=W0613
        files = []
        try:
            files = self.d_client.list_files_raw()
        except Exception:
            logger.exception("Error listing datcore files")

        return files

    @make_async
    def list_files_raw_dataset(
        self, dataset_id: str
    ) -> FileMetaDataExVec:  # pylint: disable=W0613
        files = []
        try:
            files = self.d_client.list_files_raw_dataset(dataset_id)
        except Exception:
            logger.exception("Error listing datcore files")

        return files

    @make_async
    def delete_file(self, destination: str, filename: str):
        # the object can be found in dataset/filename <-> bucket_name/object_name
        try:
            self.d_client.delete_file(destination, filename)
        except Exception:
            logger.exception("Error deleting datcore file")

    @make_async
    def delete_file_by_id(self, file_id: str):
        try:
            self.d_client.delete_file_by_id(file_id)
        except Exception:
            logger.exception("Error deleting datcore file")

    @make_async
    def download_link(self, destination: str, filename: str):
        url = ""
        try:
            url = self.d_client.download_link(destination, filename)
        except Exception:
            logger.exception("Error getting datcore download link")

        return url

    @make_async
    def download_link_by_id(self, file_id: str):
        url = ""
        filename = ""
        try:
            url, filename = self.d_client.download_link_by_id(file_id)
        except Exception:
            logger.exception("Error getting datcore download link")

        return url, filename

    @make_async
    def create_test_dataset(self, dataset):
        try:
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_files(dataset)
            else:
                ds = self.d_client.create_dataset(dataset)
            return ds.id
        except Exception:
            logger.exception("Error creating test dataset")

        return ""

    @make_async
    def delete_test_dataset(self, dataset):
        try:
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_files(dataset)
        except Exception:
            logger.exception("Error deleting test dataset")

    @make_async
    def upload_file(
        self, destination: str, local_path: str, meta_data: FileMetaData = None
    ):
        json_meta = ""
        if meta_data:
            json_meta = json.dumps(attr.asdict(meta_data))
        try:
            str_meta = json_meta
            result = False
            if str_meta:
                meta_data = json.loads(str_meta)
                result = self.d_client.upload_file(destination, local_path, meta_data)
            else:
                result = self.d_client.upload_file(destination, local_path)
            return result
        except Exception:
            logger.exception("Error uploading file to datcore")
            return False

    @make_async
    def upload_file_to_id(self, destination_id: str, local_path: str):
        _id = ""
        try:
            _id = self.d_client.upload_file_to_id(destination_id, local_path)
        except Exception:
            logger.exception("Error uploading file to datcore")

        return _id

    @make_async
    def create_collection(self, destination_id: str, collection_name: str):

        _id = ""
        try:
            _id = self.d_client.create_collection(destination_id, collection_name)
        except Exception:
            logger.exception("Error creating collection in datcore")
        return _id

    @make_async
    def list_datasets(self):
        data = []
        try:
            data = self.d_client.list_datasets()
        except Exception:
            logger.exception("Error creating collection in datcore")
        return data

    @make_async
    def ping(self):
        try:
            profile = self.d_client.profile()
            ok = profile is not None
            return ok
        except Exception:
            logger.exception("Error pinging")
            return False
