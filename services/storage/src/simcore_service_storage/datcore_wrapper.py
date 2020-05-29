import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
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

# pylint: disable=W0703


@contextmanager
def safe_call(error_msg: str = "", *, skip_logs: bool = False):
    try:
        yield
    except AttributeError:
        if not skip_logs:
            logger.warning("Calling disabled client. %s", error_msg)
    except Exception: # pylint: disable=broad-except
        if error_msg and not skip_logs:
            logger.warning(error_msg, exc_info=True)


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
    def __init__(
        self, api_token: str, api_secret: str, loop: object, pool: ThreadPoolExecutor
    ):
        self.api_token = api_token
        self.api_secret = api_secret

        self.loop = loop
        self.pool = pool

        try:
            self.d_client = DatcoreClient(
                api_token=api_token,
                api_secret=api_secret,
                host="https://api.blackfynn.io",
            )
        except Exception:
            self.d_client = None  # Disabled: any call will raise AttributeError
            logger.warning(
                "Failed to connect to datcore. Disabling client.", exc_info=True
            )

    @make_async
    def list_files_recursively(self) -> FileMetaDataVec:  # pylint: disable=W0613
        files = []

        with safe_call(error_msg="Error listing datcore files"):
            files = self.d_client.list_files_recursively()

        return files

    @make_async
    def list_files_raw(self) -> FileMetaDataExVec:  # pylint: disable=W0613
        files = []

        with safe_call(error_msg="Error listing datcore files"):
            files = self.d_client.list_files_raw()

        return files

    @make_async
    def list_files_raw_dataset(
        self, dataset_id: str
    ) -> FileMetaDataExVec:  # pylint: disable=W0613
        files = []
        with safe_call(error_msg="Error listing datcore files"):
            files = self.d_client.list_files_raw_dataset(dataset_id)

        return files

    @make_async
    def delete_file(self, destination: str, filename: str):
        # the object can be found in dataset/filename <-> bucket_name/object_name
        with safe_call(error_msg="Error deleting datcore file"):
            self.d_client.delete_file(destination, filename)

    @make_async
    def delete_file_by_id(self, file_id: str):

        with safe_call(error_msg="Error deleting datcore file"):
            self.d_client.delete_file_by_id(file_id)

    @make_async
    def download_link(self, destination: str, filename: str):
        url = ""
        with safe_call(error_msg="Error getting datcore download link"):
            url = self.d_client.download_link(destination, filename)

        return url

    @make_async
    def download_link_by_id(self, file_id: str):
        url = ""
        filename = ""
        with safe_call(error_msg="Error getting datcore download link"):
            url, filename = self.d_client.download_link_by_id(file_id)

        return url, filename

    @make_async
    def create_test_dataset(self, dataset):

        with safe_call(error_msg="Error creating test dataset"):
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_files(dataset)
            else:
                ds = self.d_client.create_dataset(dataset)
            return ds.id
        return ""

    @make_async
    def delete_test_dataset(self, dataset):

        with safe_call(error_msg="Error deleting test dataset"):
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_files(dataset)

    @make_async
    def upload_file(
        self, destination: str, local_path: str, meta_data: FileMetaData = None
    ):
        result = False
        str_meta = json.dumps(attr.asdict(meta_data)) if meta_data else ""

        with safe_call(error_msg="Error uploading file to datcore"):
            if str_meta:
                meta_data = json.loads(str_meta)
                result = self.d_client.upload_file(destination, local_path, meta_data)
            else:
                result = self.d_client.upload_file(destination, local_path)
        return result

    @make_async
    def upload_file_to_id(self, destination_id: str, local_path: str):
        _id = ""

        with safe_call(error_msg="Error uploading file to datcore"):
            _id = self.d_client.upload_file_to_id(destination_id, local_path)

        return _id

    @make_async
    def create_collection(self, destination_id: str, collection_name: str):
        _id = ""
        with safe_call(error_msg="Error creating collection in datcore"):
            _id = self.d_client.create_collection(destination_id, collection_name)
        return _id

    @make_async
    def list_datasets(self):
        data = []
        with safe_call(error_msg="Error creating collection in datcore"):
            data = self.d_client.list_datasets()
        return data

    @make_async
    def ping(self):
        ok = False
        with safe_call(skip_logs=True):
            profile = self.d_client.profile()
            ok = profile is not None
        return ok
