import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import wraps
from typing import List, Optional, Tuple

import attr

from .datcore import DatcoreClient
from .models import FileMetaData, FileMetaDataEx

logger = logging.getLogger(__name__)


@contextmanager
def safe_call(error_msg: str = "", *, skip_logs: bool = False):
    try:
        yield
    except AttributeError:
        if not skip_logs:
            logger.warning("Calling disabled client. %s", error_msg)
    except Exception:  # pylint: disable=broad-except
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
    """Wrapper to call the python2 api from datcore

    This can go away now. Next cleanup round...

    NOTE: Auto-disables client

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
        except Exception:  # pylint: disable=broad-except
            self.d_client = None  # Disabled: any call will raise AttributeError
            logger.warning("Failed to setup datcore. Disabling client.", exc_info=True)

    @property
    def is_communication_enabled(self) -> bool:
        """Wrapper class auto-disables if client cannot be created

            e.g. if endpoint service is down

        :return: True if communication with datcore is enabled
        :rtype: bool
        """
        return self.d_client is not None

    @make_async
    def list_files_recursively(self) -> List[FileMetaData]:  # pylint: disable=W0613
        files = []

        with safe_call(error_msg="Error listing datcore files"):
            files = self.d_client.list_files_recursively()

        return files

    @make_async
    def list_files_raw(self) -> List[FileMetaDataEx]:  # pylint: disable=W0613
        files = []

        with safe_call(error_msg="Error listing datcore files"):
            files = self.d_client.list_files_raw()

        return files

    @make_async
    def list_files_raw_dataset(
        self, dataset_id: str
    ) -> List[FileMetaDataEx]:  # pylint: disable=W0613
        files = []
        with safe_call(error_msg="Error listing datcore files"):
            files = self.d_client.list_files_raw_dataset(dataset_id)

        return files

    @make_async
    def delete_file(self, destination: str, filename: str) -> bool:
        # the object can be found in dataset/filename <-> bucket_name/object_name
        ok = False
        with safe_call(error_msg="Error deleting datcore file"):
            ok = self.d_client.delete_file(destination, filename)
        return ok

    @make_async
    def delete_file_by_id(self, file_id: str) -> bool:
        ok = False
        with safe_call(error_msg="Error deleting datcore file"):
            ok = self.d_client.delete_file_by_id(file_id)
        return ok

    @make_async
    def download_link(self, destination: str, filename: str) -> str:
        url = ""
        with safe_call(error_msg="Error getting datcore download link"):
            url = self.d_client.download_link(destination, filename)

        return url

    @make_async
    def download_link_by_id(self, file_id: str) -> Tuple[str, str]:
        url = ""
        filename = ""
        with safe_call(error_msg="Error getting datcore download link"):
            url, filename = self.d_client.download_link_by_id(file_id)

        return url, filename

    @make_async
    def create_test_dataset(self, dataset_name: str) -> Optional[str]:
        with safe_call(error_msg="Error creating test dataset"):
            ds = self.d_client.get_dataset(dataset_name)
            if ds is not None:
                self.d_client.delete_files(dataset_name)
            else:
                ds = self.d_client.create_dataset(dataset_name)
            return ds.id
        return None

    @make_async
    def delete_test_dataset(self, dataset) -> None:
        with safe_call(error_msg="Error deleting test dataset"):
            ds = self.d_client.get_dataset(dataset)
            if ds is not None:
                self.d_client.delete_files(dataset)

    @make_async
    def upload_file(
        self, destination: str, local_path: str, meta_data: FileMetaData = None
    ) -> bool:
        ok = False
        str_meta = json.dumps(attr.asdict(meta_data)) if meta_data else ""

        with safe_call(error_msg="Error uploading file to datcore"):
            if str_meta:
                meta_data = json.loads(str_meta)
                ok = self.d_client.upload_file(destination, local_path, meta_data)
            else:
                ok = self.d_client.upload_file(destination, local_path)
        return ok

    @make_async
    def upload_file_to_id(self, destination_id: str, local_path: str) -> Optional[str]:
        _id = None
        with safe_call(error_msg="Error uploading file to datcore"):
            _id = self.d_client.upload_file_to_id(destination_id, local_path)
        return _id

    @make_async
    def create_collection(
        self, destination_id: str, collection_name: str
    ) -> Optional[str]:
        _id = None
        with safe_call(error_msg="Error creating collection in datcore"):
            _id = self.d_client.create_collection(destination_id, collection_name)
        return _id

    @make_async
    def list_datasets(self) -> List:
        data = []
        with safe_call(error_msg="Error creating collection in datcore"):
            data = self.d_client.list_datasets()
        return data

    @make_async
    def ping(self) -> bool:
        ok = False
        with safe_call(skip_logs=True):
            profile = self.d_client.profile()
            ok = profile is not None
        return ok
