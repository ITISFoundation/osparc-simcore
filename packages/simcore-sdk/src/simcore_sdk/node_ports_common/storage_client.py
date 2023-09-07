from collections.abc import Awaitable, Callable
from functools import lru_cache, wraps
from json import JSONDecodeError
from typing import Any
from urllib.parse import quote

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from models_library.api_schemas_storage import (
    FileLocationArray,
    FileMetaDataGet,
    FileUploadSchema,
    LinkType,
    LocationID,
    PresignedLink,
    StorageFileID,
)
from models_library.basic_types import SHA256Str
from models_library.generics import Envelope
from models_library.users import UserID
from pydantic import ByteSize
from pydantic.networks import AnyUrl

from . import exceptions
from .settings import NodePortsSettings


def handle_client_exception(handler: Callable) -> Callable[..., Awaitable[Any]]:
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        try:
            return await handler(*args, **kwargs)
        except ClientResponseError as err:
            if err.status == web.HTTPNotFound.status_code:
                raise exceptions.S3InvalidPathError(
                    kwargs.get("file_id", "unknown file id")
                )
            if err.status == web.HTTPUnprocessableEntity.status_code:
                raise exceptions.StorageInvalidCall(
                    f"Invalid call to storage: {err.message}"
                )
            if 500 > err.status > 399:
                raise exceptions.StorageInvalidCall(err.message) from err
            if err.status > 500:
                raise exceptions.StorageServerIssue(err.message) from err
        except ClientConnectionError as err:
            raise exceptions.StorageServerIssue(f"{err}") from err
        except JSONDecodeError as err:
            raise exceptions.StorageServerIssue(f"{err}") from err

    return wrapped


@lru_cache
def _base_url() -> str:
    settings = NodePortsSettings.create_from_envs()
    base_url: str = settings.NODE_PORTS_STORAGE.api_base_url
    return base_url


@handle_client_exception
async def get_storage_locations(
    *, session: ClientSession, user_id: UserID
) -> FileLocationArray:
    async with session.get(
        f"{_base_url()}/locations", params={"user_id": f"{user_id}"}
    ) as response:
        response.raise_for_status()
        locations_enveloped = Envelope[FileLocationArray].parse_obj(
            await response.json()
        )
        if locations_enveloped.data is None:
            msg = "Storage server is not reponding"
            raise exceptions.StorageServerIssue(msg)
        return locations_enveloped.data


@handle_client_exception
async def get_download_file_link(
    *,
    session: ClientSession,
    file_id: StorageFileID,
    location_id: LocationID,
    user_id: UserID,
    link_type: LinkType,
) -> AnyUrl:
    """
    :raises exceptions.StorageInvalidCall
    :raises exceptions.StorageServerIssue
    """
    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}", "link_type": link_type.value},
    ) as response:
        response.raise_for_status()

        presigned_link_enveloped = Envelope[PresignedLink].parse_obj(
            await response.json()
        )
        if (
            presigned_link_enveloped.data is None
            or not presigned_link_enveloped.data.link
        ):
            msg = f"file {location_id}@{file_id} not found"
            raise exceptions.S3InvalidPathError(msg)
        url: AnyUrl = presigned_link_enveloped.data.link
        return url


@handle_client_exception
async def get_upload_file_links(
    *,
    session: ClientSession,
    file_id: StorageFileID,
    location_id: LocationID,
    user_id: UserID,
    link_type: LinkType,
    file_size: ByteSize,
    is_directory: bool,
    sha256_checksum: SHA256Str | None,
) -> FileUploadSchema:
    """
    :raises exceptions.StorageServerIssue: _description_
    :raises ClientResponseError
    """

    query_params = {
        "user_id": f"{user_id}",
        "link_type": link_type.value,
        "file_size": int(file_size),
        "is_directory": f"{is_directory}".lower(),
    }
    if sha256_checksum:
        query_params.update(sha256_checksum=str(sha256_checksum))
    async with session.put(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params=query_params,
    ) as response:
        response.raise_for_status()
        file_upload_links_enveloped = Envelope[FileUploadSchema].parse_obj(
            await response.json()
        )
    if file_upload_links_enveloped.data is None:
        msg = "Storage server is not responding"
        raise exceptions.StorageServerIssue(msg)
    return file_upload_links_enveloped.data


@handle_client_exception
async def get_file_metadata(
    *,
    session: ClientSession,
    file_id: StorageFileID,
    location_id: LocationID,
    user_id: UserID,
) -> FileMetaDataGet:
    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}/metadata",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()
        file_metadata_enveloped = Envelope[FileMetaDataGet].parse_obj(
            await response.json()
        )
        if file_metadata_enveloped.data is None:
            raise exceptions.S3InvalidPathError(file_id)
        return file_metadata_enveloped.data


@handle_client_exception
async def list_file_metadata(
    *,
    session: ClientSession,
    user_id: UserID,
    location_id: LocationID,
    uuid_filter: str,
) -> list[FileMetaDataGet]:
    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/metadata",
        params={"user_id": f"{user_id}", "uuid_filter": uuid_filter},
    ) as resp:
        resp.raise_for_status()
        envelope = Envelope[list[FileMetaDataGet]].parse_obj(await resp.json())
        assert envelope.data is not None  # nosec
        file_meta_data: list[FileMetaDataGet] = envelope.data
        return file_meta_data


@handle_client_exception
async def delete_file(
    *,
    session: ClientSession,
    file_id: StorageFileID,
    location_id: LocationID,
    user_id: UserID,
) -> None:
    async with session.delete(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()
