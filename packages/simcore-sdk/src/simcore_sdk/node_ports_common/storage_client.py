from enum import Enum
from functools import wraps
from json import JSONDecodeError
from typing import Callable
from urllib.parse import quote

from aiohttp import ClientSession, web
from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from models_library.api_schemas_storage import (
    ETag,
    FileLocationArray,
    FileMetaDataGet,
    LocationID,
    PresignedLink,
    StorageFileID,
)
from models_library.generics import Envelope
from models_library.users import UserID
from pydantic.networks import AnyUrl

from . import config, exceptions


def handle_client_exception(handler: Callable):
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        try:
            ret = await handler(*args, **kwargs)
            return ret
        except ClientResponseError as exc:
            if 500 > exc.status > 399:
                raise exceptions.StorageInvalidCall(exc.message) from exc
            if exc.status > 500:
                raise exceptions.StorageServerIssue(exc.message) from exc
        except ClientConnectionError as exc:
            raise exceptions.StorageServerIssue(f"{exc}") from exc
        except JSONDecodeError as exc:
            raise exceptions.StorageServerIssue(f"{exc}") from exc

    return wrapped


def _base_url() -> str:
    return f"http://{config.STORAGE_ENDPOINT}/{config.STORAGE_VERSION}"


@handle_client_exception
async def get_storage_locations(
    session: ClientSession, user_id: UserID
) -> FileLocationArray:
    if not isinstance(user_id, int) or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}' is invalid",
        )

    async with session.get(
        f"{_base_url()}/locations", params={"user_id": f"{user_id}"}
    ) as response:
        response.raise_for_status()
        locations_enveloped = Envelope[FileLocationArray].parse_obj(
            await response.json()
        )
        if locations_enveloped.data is None:
            raise exceptions.StorageServerIssue("Storage server is not reponding")
        return locations_enveloped.data


class LinkType(str, Enum):
    PRESIGNED = "presigned"
    S3 = "s3"


@handle_client_exception
async def get_download_file_link(
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
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are not allowed to be empty",
        )

    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}", "link_type": link_type.value},
    ) as response:
        if response.status == web.HTTPNotFound.status_code:
            raise exceptions.S3InvalidPathError(
                f"file {location_id}@{file_id} not found"
            )
        response.raise_for_status()

        presigned_link_enveloped = Envelope[PresignedLink].parse_obj(
            await response.json()
        )
        if presigned_link_enveloped.data is None:
            raise exceptions.S3InvalidPathError(
                f"file {location_id}@{file_id} not found"
            )
        return presigned_link_enveloped.data.link


@handle_client_exception
async def get_upload_file_link(
    session: ClientSession,
    file_id: StorageFileID,
    location_id: LocationID,
    user_id: UserID,
    link_type: LinkType,
) -> AnyUrl:
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are not allowed to be empty",
        )
    async with session.put(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}", "link_type": link_type.value},
    ) as response:
        response.raise_for_status()

        presigned_link_enveloped = Envelope[PresignedLink].parse_obj(
            await response.json()
        )
        if presigned_link_enveloped.data is None:
            raise exceptions.StorageServerIssue("Storage server is not reponding")
        return presigned_link_enveloped.data.link


@handle_client_exception
async def get_file_metadata(
    session: ClientSession,
    file_id: StorageFileID,
    location_id: LocationID,
    user_id: UserID,
) -> FileMetaDataGet:
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are not allowed to be empty",
        )
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
async def delete_file(
    session: ClientSession,
    file_id: StorageFileID,
    location_id: LocationID,
    user_id: UserID,
) -> None:
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are not allowed to be empty",
        )
    async with session.delete(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()


@handle_client_exception
async def update_file_meta_data(
    session: ClientSession, s3_object: StorageFileID, user_id: UserID
) -> ETag:
    url = f"{_base_url()}/locations/0/files/{quote(s3_object, safe='')}/metadata"
    result = await session.patch(url, params=dict(user_id=user_id))
    if result.status != web.HTTPOk.status_code:
        raise exceptions.StorageInvalidCall(
            f"Could not fetch metadata: status={result.status} {await result.text()}"
        )

    response = await result.json()
    return response["data"]["entity_tag"]
