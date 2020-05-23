#pylint: disable=too-many-arguments
import logging
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from aiohttp import ClientSession
from yarl import URL

import aiofiles
from simcore_service_storage_sdk import ApiClient, Configuration, UsersApi
from simcore_service_storage_sdk.rest import ApiException

from . import config, exceptions

log = logging.getLogger(__name__)

CHUNK_SIZE = 1*1024*1024


class ClientSessionContextManager:
    #
    # NOTE: creating a session at every call is inneficient and a persistent session
    # per app is recommended.
    # This package has no app so session is passed as optional arguments
    # See https://github.com/ITISFoundation/osparc-simcore/issues/1098
    #
    def __init__(self, session=None):
        self.active_session = session or ClientSession()
        self.is_owned = session is None

    async def __aenter__(self):
        return self.active_session

    async def __aexit__(self, exc_type, exc, tb):
        if self.is_owned and self.active_session is not None:
            warnings.warn("Optional session will be deprecated, pass instead controled session (e.g. from app[APP_CLIENT_SESSION_KEY])",
                category=DeprecationWarning)
            await self.active_session.close()


@contextmanager
def api_client():
    cfg = Configuration()
    cfg.host = "http://{}/{}".format(config.STORAGE_ENDPOINT, config.STORAGE_VERSION)
    log.debug("api connects using %s", cfg.host)
    client = ApiClient(cfg)
    try:
        yield client
    except ApiException:
        log.exception(msg="connection to storage service failed")
    finally:
        del client.rest_client

def _handle_api_exception(store_id:str, err: ApiException):
    if err.status > 399 and err.status < 500:
        # something invalid
        raise exceptions.StorageInvalidCall(err)
    if err.status > 499:
        # something went bad inside the storage server
        raise exceptions.StorageServerIssue(err)
    raise exceptions.StorageConnectionError(store_id, err)

async def _get_location_id_from_location_name(store:str, api:UsersApi):
    try:
        resp = await api.get_storage_locations(user_id=config.USER_ID)
        for location in resp.data:
            if location["name"] == store:
                return location["id"]
        # location id not found
        raise exceptions.S3InvalidStore(store)
    except ApiException as err:
        _handle_api_exception(store, err)
    if resp.error:
        raise exceptions.StorageConnectionError(store, resp.error.to_str())

async def _get_link(store_id:int, file_id:str, apifct) -> URL:
    log.debug("Getting link from store id %s for %s", store_id, file_id)
    try:
        resp = await apifct(location_id=store_id, user_id=config.USER_ID, file_id=file_id)

        if resp.error:
            raise exceptions.S3TransferError("Error getting link: {}".format(resp.error.to_str()))
        if not resp.data.link:
            raise exceptions.S3InvalidPathError(file_id)
        log.debug("Got link %s", resp.data.link)
        return URL(resp.data.link)
    except ApiException as err:
        _handle_api_exception(store_id, err)

async def _get_download_link(store_id:int, file_id:str, api:UsersApi) -> URL:
    return await _get_link(store_id, file_id, api.download_file)

async def _get_upload_link(store_id:int, file_id:str, api:UsersApi) -> URL:
    return await _get_link(store_id, file_id, api.upload_file)

async def _download_link_to_file(session:ClientSession, url:URL, file_path:Path, store: str, s3_object: str):
    log.debug("Downloading from %s to %s", url, file_path)
    async with session.get(url) as response:
        if response.status == 404:
            raise exceptions.S3InvalidPathError(s3_object)
        if response.status > 299:
            raise exceptions.S3TransferError("Error when downloading {} from {} using {}".format(s3_object, store, url))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, 'wb') as file_pointer:
            # await file_pointer.write(await response.read())
            chunk = await response.content.read(CHUNK_SIZE)
            while chunk:
                await file_pointer.write(chunk)
                chunk = await response.content.read(CHUNK_SIZE)
        log.debug("Download complete")
        return await response.release()

async def _file_sender(file_path:Path):
    async with aiofiles.open(file_path, 'rb') as file_pointer:
        chunk = await file_pointer.read(CHUNK_SIZE)
        while chunk:
            yield chunk
            chunk = await file_pointer.read(CHUNK_SIZE)

async def _upload_file_to_link(session: ClientSession, url: URL, file_path: Path):
    log.debug("Uploading from %s to %s", file_path, url)
    async with session.put(url, data=file_path.open('rb')) as resp:
        if resp.status > 299:
            response_text = await resp.text()
            raise exceptions.S3TransferError("Could not upload file {}:{}".format(file_path, response_text))

async def download_file(*, store_name: str=None, store_id:str=None, s3_object:str, local_folder: Path, session: Optional[ClientSession]=None) -> Path:
    """ Downloads a file to S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :return: path to downloaded file
    """
    log.debug("Downloading from store %s:id %s, s3 object %s, to %s", store_name, store_id, s3_object, local_folder)
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")

    download_link = None
    with api_client() as client:
        api = UsersApi(client)

        if store_name is not None:
            store_id = await _get_location_id_from_location_name(store_name, api)
        download_link = await _get_download_link(store_id, s3_object, api)
    # the link contains the file name
    if download_link:
        # a download link looks something like:
        # http://172.16.9.89:9001/simcore-test/269dec55-6d18-4901-a767-b567db23d425/4ccf4e2e-a6cd-4f77-a255-4c36fa1b1c72/test.test?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=s3access/20190719/us-east-1/s3/aws4_request&X-Amz-Date=20190719T142431Z&X-Amz-Expires=259200&X-Amz-SignedHeaders=host&X-Amz-Signature=90268f3b580b38c1aad128475936c6f5fd335d11d01ec143cca1056d92a724b5
        local_file_path = local_folder / Path(download_link.path).name
        # remove an already existing file if present
        if local_file_path.exists():
            local_file_path.unlink()

        async with ClientSessionContextManager(session) as active_session:
            await _download_link_to_file(active_session, download_link, local_file_path, store_id, s3_object)

        return local_file_path

    raise exceptions.S3InvalidPathError(s3_object)



async def upload_file(*, store_id:str=None, store_name:str=None, s3_object:str, local_file_path:Path, session: Optional[ClientSession]=None) -> str:
    """ Uploads a file to S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :return: stored id
    """
    log.debug("Trying to upload file to S3: store name %s, store id %s, s3object %s, file path %s", store_name, store_id, s3_object, local_file_path)
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")
    with api_client() as client:
        api = UsersApi(client)

        if store_name is not None:
            store_id = await _get_location_id_from_location_name(store_name, api)
        upload_link = await _get_upload_link(store_id, s3_object, api)

        if upload_link:
            upload_link = URL(upload_link)

            async with ClientSessionContextManager(session) as active_session:
                await _upload_file_to_link(active_session, upload_link, local_file_path)

            return store_id

    raise exceptions.S3InvalidPathError(s3_object)
