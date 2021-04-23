import json

# pylint: disable=too-many-arguments
import logging
import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Tuple, Union

import aiofiles
from aiohttp import ClientPayloadError, ClientSession, ClientTimeout
from models_library.settings.services_common import ServicesCommonSettings
from simcore_service_storage_sdk import ApiClient, Configuration, UsersApi
from simcore_service_storage_sdk.rest import ApiException
from tqdm import tqdm
from yarl import URL

from ..config.http_clients import client_request_settings
from . import config, exceptions

log = logging.getLogger(__name__)

CHUNK_SIZE = 1 * 1024 * 1024


class ClientSessionContextManager:
    #
    # NOTE: creating a session at every call is inneficient and a persistent session
    # per app is recommended.
    # This package has no app so session is passed as optional arguments
    # See https://github.com/ITISFoundation/osparc-simcore/issues/1098
    #
    def __init__(self, session=None):
        # We are interested in fast connections, if a connection is established
        # there is no timeout for file download operations

        self.active_session = session or ClientSession(
            timeout=ClientTimeout(
                total=None,
                connect=client_request_settings.aiohttp_connect_timeout,
                sock_connect=client_request_settings.aiohttp_sock_connect_timeout,
            )
        )
        self.is_owned = self.active_session is not session

    async def __aenter__(self):
        return self.active_session

    async def __aexit__(self, exc_type, exc, tb):
        if self.is_owned:
            warnings.warn(
                "Optional session will be deprecated, pass instead controled session (e.g. from app[APP_CLIENT_SESSION_KEY])",
                category=DeprecationWarning,
            )
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
        del client


def _handle_api_exception(store_id: Union[int, str], err: ApiException):
    """ Maps client's ApiException -> NodeportsException """

    #  NOTE: ApiException produces a long __str__ with multiple lines which is not
    #  allowed when composing header
    #  SEE https://github.com/tornadoweb/tornado/blob/master/tornado/http1connection.py#L456
    error_reason: str = err.reason.replace("\n", "-")

    if err.status > 399 and err.status < 500:
        # something invalid
        raise exceptions.StorageInvalidCall(error_reason)
    if err.status > 499:
        # something went bad inside the storage server
        raise exceptions.StorageServerIssue(error_reason)
    raise exceptions.StorageConnectionError(store_id, error_reason)


async def _get_location_id_from_location_name(store: str, api: UsersApi):
    try:
        resp = await api.get_storage_locations(user_id=config.USER_ID)
        for location in resp.data:
            if location["name"] == store:
                return location["id"]
        # location id not found
        raise exceptions.S3InvalidStore(store)
    except ApiException as err:
        _handle_api_exception(store, err)


async def _get_link(store_id: int, file_id: str, apifct) -> URL:
    log.debug("Getting link from store id %s for %s", store_id, file_id)
    # When uploading and downloading files from the storage service
    # it is important to use a longer timeout, previously was 5 minutes
    # changing to 1 hour. this will allow for larger payloads to be stored/download
    resp = await apifct(
        location_id=store_id,
        user_id=config.USER_ID,
        file_id=file_id,
        _request_timeout=ServicesCommonSettings().storage_service_upload_download_timeout,
    )

    if resp.error:
        raise exceptions.S3TransferError(
            "Error getting link: {}".format(resp.error.to_str())
        )
    if not resp.data.link:
        raise exceptions.S3InvalidPathError(file_id)
    log.debug("Got link %s", resp.data.link)
    return URL(resp.data.link)


async def _get_download_link(store_id: int, file_id: str, api: UsersApi) -> URL:
    try:
        return await _get_link(store_id, file_id, api.download_file)
    except ApiException as err:
        if err.status == 404:
            raise exceptions.InvalidDownloadLinkError(None) from err
        _handle_api_exception(store_id, err)


async def _get_upload_link(store_id: int, file_id: str, api: UsersApi) -> URL:
    try:
        return await _get_link(store_id, file_id, api.upload_file)
    except ApiException as err:
        _handle_api_exception(store_id, err)


async def _download_link_to_file(session: ClientSession, url: URL, file_path: Path):
    log.debug("Downloading from %s to %s", url, file_path)
    async with session.get(url) as response:
        if response.status == 404:
            raise exceptions.InvalidDownloadLinkError(url)
        if response.status > 299:
            raise exceptions.TransferError(url)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Length
        file_size = int(response.headers.get("Content-Length", 0)) or None
        try:
            with tqdm(
                desc=f"downloading {file_path} [{file_size} bytes]",
                total=file_size,
                unit="byte",
                unit_scale=True,
            ) as pbar:
                async with aiofiles.open(file_path, "wb") as file_pointer:
                    chunk = await response.content.read(CHUNK_SIZE)
                    while chunk:
                        await file_pointer.write(chunk)
                        pbar.update(len(chunk))
                        chunk = await response.content.read(CHUNK_SIZE)
                log.debug("Download complete")
        except ClientPayloadError as exc:
            raise exceptions.TransferError(url) from exc


ETag = str


async def _upload_file_to_link(
    session: ClientSession, url: URL, file_path: Path
) -> Optional[ETag]:
    log.debug("Uploading from %s to %s", file_path, url)
    file_size = file_path.stat().st_size

    async def file_sender(file_name: Path):
        with tqdm(
            desc=f"uploading {file_path} [{file_size} bytes]",
            total=file_size,
            unit="byte",
            unit_scale=True,
        ) as pbar:
            async with aiofiles.open(file_name, "rb") as f:
                chunk = await f.read(CHUNK_SIZE)
                while chunk:
                    pbar.update(len(chunk))
                    yield chunk
                    chunk = await f.read(CHUNK_SIZE)

    data_provider = file_sender(file_path)
    headers = {"Content-Length": f"{file_size}"}

    async with session.put(url, data=data_provider, headers=headers) as resp:
        if resp.status > 299:
            response_text = await resp.text()
            raise exceptions.S3TransferError(
                "Could not upload file {}:{}".format(file_path, response_text)
            )
        if resp.status != 200:
            response_text = await resp.text()
            raise exceptions.S3TransferError(
                "Issue when uploading file {}:{}".format(file_path, response_text)
            )

        # get the S3 etag from the headers
        e_tag = json.loads(resp.headers.get("Etag", None))
        log.debug("Uploaded %s to %s, received Etag %s", file_path, url, e_tag)
        return e_tag


async def download_file_from_s3(
    *,
    store_name: str = None,
    store_id: str = None,
    s3_object: str,
    local_folder: Path,
    session: Optional[ClientSession] = None,
) -> Path:
    """Downloads a file from S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :return: path to downloaded file
    """
    log.debug(
        "Downloading from store %s:id %s, s3 object %s, to %s",
        store_name,
        store_id,
        s3_object,
        local_folder,
    )
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")

    # get the s3 link
    download_link = None
    with api_client() as client:
        api = UsersApi(client)

        if store_name is not None:
            store_id = await _get_location_id_from_location_name(store_name, api)
        download_link = await _get_download_link(store_id, s3_object, api)
    # the link contains the file name
    if not download_link:
        raise exceptions.S3InvalidPathError(s3_object)

    return await download_file_from_link(download_link, local_folder, session)


async def download_file_from_link(
    download_link: URL,
    destination_folder: Path,
    session: Optional[ClientSession] = None,
    file_name: Optional[str] = None,
) -> Path:
    # a download link looks something like:
    # http://172.16.9.89:9001/simcore-test/269dec55-6d18-4901-a767-b567db23d425/4ccf4e2e-a6cd-4f77-a255-4c36fa1b1c72/test.test?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=s3access/20190719/us-east-1/s3/aws4_request&X-Amz-Date=20190719T142431Z&X-Amz-Expires=259200&X-Amz-SignedHeaders=host&X-Amz-Signature=90268f3b580b38c1aad128475936c6f5fd335d11d01ec143cca1056d92a724b5
    local_file_path = destination_folder / (file_name or Path(download_link.path).name)

    # remove an already existing file if present
    if local_file_path.exists():
        local_file_path.unlink()

    async with ClientSessionContextManager(session) as active_session:
        await _download_link_to_file(active_session, download_link, local_file_path)

    return local_file_path


async def upload_file(
    *,
    store_id: Optional[str] = None,
    store_name: Optional[str] = None,
    s3_object: str,
    local_file_path: Path,
    session: Optional[ClientSession] = None,
) -> Tuple[str, str]:
    """Uploads a file to S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :return: stored id
    """
    log.debug(
        "Trying to upload file to S3: store name %s, store id %s, s3object %s, file path %s",
        store_name,
        store_id,
        s3_object,
        local_file_path,
    )
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")
    with api_client() as client:
        api = UsersApi(client)

        if store_name is not None:
            store_id = await _get_location_id_from_location_name(store_name, api)
        upload_link: URL = await _get_upload_link(store_id, s3_object, api)

        if upload_link:
            # FIXME: This client should be kept with the nodeports instead of creating one each time
            async with ClientSessionContextManager(session) as active_session:
                e_tag = await _upload_file_to_link(
                    active_session, upload_link, local_file_path
                )
                return store_id, e_tag

    raise exceptions.S3InvalidPathError(s3_object)


async def entry_exists(store_id: str, s3_object: str) -> bool:
    """Returns True if metadata for s3_object is present"""
    user_id = config.USER_ID
    with api_client() as client:
        api = UsersApi(client)
        try:
            log.debug("Will request metadata for s3_object=%s", s3_object)
            result = await api.get_file_metadata(s3_object, store_id, user_id)
            log.debug("Result for metadata s3_object=%s, result=%s", s3_object, result)
            is_metadata_present = result.data.object_name == s3_object
            return is_metadata_present
        except Exception as e:  # pylint: disable=broad-except
            log.exception(
                "Could not find metadata for requested store_id=%s s3_object=%s",
                store_id,
                s3_object,
            )
            raise exceptions.NodeportsException(msg=str(e))
