import json

# pylint: disable=too-many-arguments
import logging
from pathlib import Path
from typing import Optional, Tuple

import aiofiles
from aiohttp import ClientPayloadError, ClientSession
from pydantic.networks import AnyUrl
from tqdm import tqdm
from yarl import URL

from ..node_ports_common.client_session_manager import ClientSessionContextManager
from . import exceptions, storage_client

log = logging.getLogger(__name__)

CHUNK_SIZE = 1 * 1024 * 1024


async def _get_location_id_from_location_name(
    user_id: int,
    store: str,
    session: ClientSession,
) -> str:
    resp = await storage_client.get_storage_locations(session, user_id)
    for location in resp:
        if location.name == store:
            return f"{location.id}"
    # location id not found
    raise exceptions.S3InvalidStore(store)


async def _get_download_link(
    user_id: int,
    store_id: str,
    file_id: str,
    session: ClientSession,
) -> URL:
    presigned_link: AnyUrl = await storage_client.get_download_file_presigned_link(
        session, file_id, store_id, user_id
    )
    if not presigned_link:
        raise exceptions.S3InvalidPathError(file_id)

    return URL(presigned_link)


async def _get_upload_link(
    user_id: int,
    store_id: str,
    file_id: str,
    session: ClientSession,
) -> URL:
    presigned_link: AnyUrl = await storage_client.get_upload_file_presigned_link(
        session, file_id, store_id, user_id
    )
    if not presigned_link:
        raise exceptions.S3InvalidPathError(file_id)

    return URL(presigned_link)


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
) -> ETag:
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
        e_tag = json.loads(resp.headers.get("Etag", ""))
        log.debug("Uploaded %s to %s, received Etag %s", file_path, url, e_tag)
        return e_tag


async def get_download_link_from_s3(
    *,
    user_id: int,
    store_name: str = None,
    store_id: str = None,
    s3_object: str,
    client_session: Optional[ClientSession] = None,
) -> Optional[URL]:
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")

    async with ClientSessionContextManager(client_session) as session:
        if store_name is not None:
            store_id = await _get_location_id_from_location_name(
                user_id, store_name, session
            )
        assert store_id is not None  # nosec
        return await _get_download_link(user_id, store_id, s3_object, session)


async def get_upload_link_from_s3(
    *,
    user_id: int,
    store_name: str = None,
    store_id: str = None,
    s3_object: str,
    client_session: Optional[ClientSession] = None,
) -> Tuple[str, URL]:
    if store_name is None and store_id is None:
        raise exceptions.NodeportsException(msg="both store name and store id are None")

    async with ClientSessionContextManager(client_session) as session:
        if store_name is not None:
            store_id = await _get_location_id_from_location_name(
                user_id, store_name, session
            )
        assert store_id is not None  # nosec
        return (
            store_id,
            await _get_upload_link(user_id, store_id, s3_object, session),
        )


async def download_file_from_s3(
    *,
    user_id: int,
    store_name: str = None,
    store_id: str = None,
    s3_object: str,
    local_folder: Path,
    client_session: Optional[ClientSession] = None,
) -> Path:
    """Downloads a file from S3

    :param session: add app[APP_CLIENT_SESSION_KEY] session here otherwise default is opened/closed every call
    :type session: ClientSession, optional
    :raises exceptions.S3InvalidPathError
    :raises exceptions.StorageInvalidCall
    :return: path to downloaded file
    """
    log.debug(
        "Downloading from store %s:id %s, s3 object %s, to %s",
        store_name,
        store_id,
        s3_object,
        local_folder,
    )

    async with ClientSessionContextManager(client_session) as session:
        # get the s3 link
        download_link = await get_download_link_from_s3(
            user_id=user_id,
            store_name=store_name,
            store_id=store_id,
            s3_object=s3_object,
            client_session=session,
        )

        # the link contains the file name
        if not download_link:
            raise exceptions.S3InvalidPathError(s3_object)

        return await download_file_from_link(
            download_link,
            local_folder,
            client_session=session,
        )


async def download_file_from_link(
    download_link: URL,
    destination_folder: Path,
    file_name: Optional[str] = None,
    client_session: Optional[ClientSession] = None,
) -> Path:
    # a download link looks something like:
    # http://172.16.9.89:9001/simcore-test/269dec55-6d18-4901-a767-b567db23d425/4ccf4e2e-a6cd-4f77-a255-4c36fa1b1c72/test.test?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=s3access/20190719/us-east-1/s3/aws4_request&X-Amz-Date=20190719T142431Z&X-Amz-Expires=259200&X-Amz-SignedHeaders=host&X-Amz-Signature=90268f3b580b38c1aad128475936c6f5fd335d11d01ec143cca1056d92a724b5
    local_file_path = destination_folder / (file_name or Path(download_link.path).name)

    # remove an already existing file if present
    if local_file_path.exists():
        local_file_path.unlink()

    async with ClientSessionContextManager(client_session) as session:
        await _download_link_to_file(session, download_link, local_file_path)

    return local_file_path


async def upload_file(
    *,
    user_id: int,
    store_id: Optional[str] = None,
    store_name: Optional[str] = None,
    s3_object: str,
    local_file_path: Path,
    client_session: Optional[ClientSession] = None,
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
    async with ClientSessionContextManager(client_session) as session:
        store_id, upload_link = await get_upload_link_from_s3(
            user_id=user_id,
            store_name=store_name,
            store_id=store_id,
            s3_object=s3_object,
            client_session=session,
        )

        if not upload_link:
            raise exceptions.S3InvalidPathError(s3_object)

        e_tag = await _upload_file_to_link(session, upload_link, local_file_path)
        return store_id, e_tag


async def entry_exists(
    user_id: int,
    store_id: str,
    s3_object: str,
    client_session: Optional[ClientSession] = None,
) -> bool:
    """Returns True if metadata for s3_object is present"""
    try:
        async with ClientSessionContextManager(client_session) as session:
            log.debug("Will request metadata for s3_object=%s", s3_object)

            result = await storage_client.get_file_metadata(
                session, s3_object, store_id, user_id
            )
            log.debug("Result for metadata s3_object=%s, result=%s", s3_object, result)
            return result.get("object_name") == s3_object if result else False
    except exceptions.S3InvalidPathError:
        return False


async def get_file_metadata(
    user_id: int,
    store_id: str,
    s3_object: str,
    client_session: Optional[ClientSession] = None,
) -> Tuple[str, str]:
    async with ClientSessionContextManager(client_session) as session:
        log.debug("Will request metadata for s3_object=%s", s3_object)
        result = await storage_client.get_file_metadata(
            session, s3_object, store_id, user_id
        )
    if not result:
        raise exceptions.StorageInvalidCall(f"The file '{s3_object}' cannot be found")
    log.debug("Result for metadata s3_object=%s, result=%s", s3_object, result)
    return (f"{result.get('location_id', '')}", result.get("entity_tag", ""))


async def delete_file(
    user_id: int,
    store_id: str,
    s3_object: str,
    client_session: Optional[ClientSession] = None,
) -> None:
    async with ClientSessionContextManager(client_session) as session:
        log.debug("Will delete file for s3_object=%s", s3_object)
        await storage_client.delete_file(session, s3_object, store_id, user_id)
