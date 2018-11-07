import logging
from contextlib import contextmanager
from pathlib import Path

import aiofiles
import aiohttp
import async_timeout
from yarl import URL

from simcore_sdk.nodeports import config, exceptions
from simcore_service_storage_sdk import ApiClient, Configuration, UsersApi
from simcore_service_storage_sdk.rest import ApiException

log = logging.getLogger(__name__)



@contextmanager
def api_client():
    cfg = Configuration()
    cfg.host = cfg.host.format(
        host=config.STORAGE_HOST,
        port=config.STORAGE_PORT,
        basePath=config.STORAGE_VERSION
    )

    client = ApiClient(cfg)
    try:
        yield client
    except ApiException:
        log.exception(msg="connection to storage service failed")
    del client.rest_client

def _handle_api_exception(store:str, err: ApiException):
    if err.status > 399 and err.status < 500:
        # something invalid
        raise exceptions.StorageInvalidCall(err)
    elif err.status > 499:
        # something went bad inside the storage server
        raise exceptions.StorageServerIssue(err)
    else:
        raise exceptions.StorageConnectionError(store, err)
    

async def _get_location_id_from_location_name(store:str, api:UsersApi):
    try:
        resp = await api.get_storage_locations(user_id=config.USER_ID)
        for location in resp.data:
            if location.name == store:
                return location.id
        # location id not found
        raise exceptions.S3InvalidStore(store)
    except ApiException as err:
        _handle_api_exception(store, err)
    if resp.error:
        raise exceptions.StorageConnectionError(store, resp.error.to_str())
    

async def _get_link(store:str, location_id:int, file_id:str, apifct):
    log.debug("Getting link from %s, %s, %s", store, location_id, file_id)
    try:
        resp = await apifct(location_id=location_id, user_id=config.USER_ID, file_id=file_id)
        
        if resp.error:
            raise exceptions.S3TransferError("Error getting link: {}".format(resp.error.to_str()))
        if not resp.data.link:
            raise exceptions.S3InvalidPathError(file_id)
        log.debug("Got link %s", resp.data.link)
        return resp.data.link
    except ApiException as err:
        _handle_api_exception(store, err)

async def _get_download_link(store:str, location_id:int, file_id:str, api:UsersApi):
    return await _get_link(store, location_id, file_id, api.download_file)

async def _get_upload_link(store:str, location_id:int, file_id:str, api:UsersApi):
    return await _get_link(store, location_id, file_id, api.upload_file)

async def _download_link_to_file(session:aiohttp.ClientSession, url:URL, file_path:Path, store: str, s3_object: str):
    log.debug("Downloading from %s to %s", url, file_path)
    with async_timeout.timeout(10):
        async with session.get(url) as response:
            if response.status == 404:
                raise exceptions.S3InvalidPathError(s3_object)
            if response.status != 200:
                raise exceptions.S3TransferError("Error when downloading {} from {} using {}".format(s3_object, store, url))
            file_path.parent.mkdir(exist_ok=True)
            with file_path.open('wb') as f_handle:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    f_handle.write(chunk)
            log.debug("Download complete")
            return await response.release()

async def _file_sender(file_path:Path):
    # with async_timeout.timeout(10):
    async with aiofiles.open(file_path, 'rb') as file_pointer:
        chunk = await file_pointer.read(1024)
        while chunk:
            yield chunk
            chunk = await file_pointer.read(1024)

async def _upload_file_to_link(session: aiohttp.ClientSession, url: URL, file_path: Path):
    log.debug("Uploading from %s to %s", file_path, url)
    # async with session.put(url, data=_file_sender(file_path)) as resp:
    async with session.put(url, data=file_path.open('rb')) as resp:
        if resp.status > 299:
            raise exceptions.S3TransferError("Could not upload file {}".format(file_path))
        

async def download_file_from_S3(store: str, s3_object: str, file_path: Path):
    log.debug("Trying to download from S3: store %s, s3 object %s, file name %s", store, s3_object, file_path)
    with api_client() as client:
        api = UsersApi(client)
        
        location_id = await _get_location_id_from_location_name(store, api)
        download_link = await _get_download_link(store, location_id, s3_object, api)

        if download_link:
            download_link = URL(download_link)
            # remove an already existing file if present
            # FIXME: if possible we should compare the files if the download needs to take place or not
            if file_path.exists():
                file_path.unlink()    
            async with aiohttp.ClientSession() as session:
                await _download_link_to_file(session, download_link, file_path, store, s3_object)
            return file_path

    raise exceptions.S3InvalidPathError(s3_object)

async def upload_file_to_s3(store:str, s3_object:str, file_path:Path):
    log.debug("Trying to upload file to S3: store %s, s3ovject %s, file path %s", store, s3_object, file_path)
    with api_client() as client:
        api = UsersApi(client)
        
        location_id = await _get_location_id_from_location_name(store, api)
        upload_link = await _get_upload_link(store, location_id, s3_object, api)

        if upload_link:
            upload_link = URL(upload_link)

            async with aiohttp.ClientSession() as session:
                await _upload_file_to_link(session, upload_link, file_path)                
                return s3_object

    raise exceptions.S3InvalidPathError(s3_object)
