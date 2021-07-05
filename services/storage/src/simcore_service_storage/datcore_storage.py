import asyncio
import logging
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from blackfynn.base import UnauthorizedException
from servicelib.aiopg_utils import PostgresRetryPolicyUponOperation

from .abc_storage import DataStorageInterface
from .constants import DATCORE_ID, DATCORE_STR, SIMCORE_S3_ID, SIMCORE_S3_STR
from .datcore_wrapper import DatcoreWrapper
from .models import DatasetMetaData, FileMetaData, FileMetaDataEx

logger = logging.getLogger(__name__)

postgres_service_retry_policy_kwargs = PostgresRetryPolicyUponOperation(logger).kwargs


@dataclass
class DatCoreApiToken:
    api_token: Optional[str] = None
    api_secret: Optional[str] = None

    def to_tuple(self):
        return (self.api_token, self.api_secret)


@dataclass
class DatCoreStorage(DataStorageInterface):
    """Access to DAT-CORE storage"""

    # TODO: perhaps can be used a cache? add a lifetime?
    datcore_tokens: Dict[str, DatCoreApiToken]
    pool: ThreadPoolExecutor

    def _get_datcore_tokens(self, user_id: str) -> Tuple[str, str]:
        # pylint: disable=no-member
        assert hasattr(self.datcore_tokens, "get")  # nosec
        token = self.datcore_tokens.get(user_id, DatCoreApiToken())
        return token.to_tuple()

    async def locations(self, user_id: str):
        locs = []
        simcore_s3 = {"name": SIMCORE_S3_STR, "id": SIMCORE_S3_ID}
        locs.append(simcore_s3)

        ping_ok = await self.ping_datcore(user_id=user_id)
        if ping_ok:
            datcore = {"name": DATCORE_STR, "id": DATCORE_ID}
            locs.append(datcore)

        return locs

    async def ping_datcore(self, user_id: str) -> bool:
        """Checks whether user account in datcore is accesible

        :param user_id: user identifier
        :type user_id: str
        :return: True if user can access his datcore account
        :rtype: bool
        """

        api_token, api_secret = self._get_datcore_tokens(user_id)
        logger.info("token: %s, secret %s", api_token, api_secret)
        if api_token:
            try:
                dcw = DatcoreWrapper(
                    api_token, api_secret, asyncio.get_event_loop(), self.pool
                )
                profile = await dcw.ping()
                if profile:
                    return True
            except UnauthorizedException:
                logger.exception("Connection to datcore not possible")

        return False

    # LIST/GET ---------------------------

    async def list_files(
        self,
        user_id: Union[str, int],
        location: str,
        uuid_filter: str = "",
        regex: str = "",
    ) -> List[FileMetaDataEx]:
        """Returns a list of file paths

        - Works for simcore.s3 and datcore
        - Can filter on uuid: useful to filter on project_id/node_id
        - Can filter upon regular expression (for now only on key: value pairs of the FileMetaData)
        """
        data = deque()
        assert location == DATCORE_STR
        api_token, api_secret = self._get_datcore_tokens(user_id)
        dcw = DatcoreWrapper(api_token, api_secret, asyncio.get_event_loop(), self.pool)
        data = await dcw.list_files_raw()

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
        assert location == DATCORE_STR

        api_token, api_secret = self._get_datcore_tokens(user_id)
        dcw = DatcoreWrapper(api_token, api_secret, asyncio.get_event_loop(), self.pool)
        data: List[FileMetaData] = await dcw.list_files_raw_dataset(dataset_id)

        return data

    async def list_datasets(self, user_id: str, location: str) -> List[DatasetMetaData]:
        """Returns a list of top level datasets

        Works for simcore.s3 and datcore

        """
        data = []

        assert location == DATCORE_STR
        api_token, api_secret = self._get_datcore_tokens(user_id)
        dcw = DatcoreWrapper(api_token, api_secret, asyncio.get_event_loop(), self.pool)
        data = await dcw.list_datasets()

        return data

    async def list_file(
        self, user_id: str, location: str, file_uuid: str
    ) -> Optional[FileMetaDataEx]:

        assert location == DATCORE_STR

        # FIXME: review return inconsistencies
        api_token, api_secret = self._get_datcore_tokens(user_id)
        _dcw = DatcoreWrapper(
            api_token, api_secret, asyncio.get_event_loop(), self.pool
        )
        data = []  # await _dcw.list_file(file_uuid)
        return data

    # UPLOAD/DOWNLOAD LINKS ---------------------------

    async def upload_file_to_datcore(
        self, user_id: str, local_file_path: str, destination_id: str
    ):
        # uploads a locally available file to dat core given the storage path, optionally attached some meta data
        api_token, api_secret = self._get_datcore_tokens(user_id)
        dcw = DatcoreWrapper(api_token, api_secret, asyncio.get_event_loop(), self.pool)
        await dcw.upload_file_to_id(destination_id, local_file_path)

    async def download_link_datcore(
        self, user_id: str, file_id: str
    ) -> Tuple[str, str]:
        link, filename = "", ""
        api_token, api_secret = self._get_datcore_tokens(user_id)
        dcw = DatcoreWrapper(api_token, api_secret, asyncio.get_event_loop(), self.pool)
        link, filename = await dcw.download_link_by_id(file_id)
        return link, filename

    # DELETE -------------------------------------

    async def delete_file(self, user_id: str, location: str, file_uuid: str):
        """Deletes a file given its fmd and location

        Additionally requires a user_id for 3rd party auth

        For internal storage, the db state should be updated upon completion via
        Notification mechanism

        For simcore.s3 we can use the file_name
        For datcore we need the full path
        """
        assert location == DATCORE_STR

        # FIXME: review return inconsistencies
        api_token, api_secret = self._get_datcore_tokens(user_id)
        dcw = DatcoreWrapper(api_token, api_secret, asyncio.get_event_loop(), self.pool)
        # destination, filename = _parse_datcore(file_uuid)
        file_id = file_uuid
        return await dcw.delete_file_by_id(file_id)
