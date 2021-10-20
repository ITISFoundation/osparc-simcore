from functools import wraps
from json import JSONDecodeError
from typing import Any, Callable, Dict
from urllib.parse import quote

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from models_library.api_schemas_storage import (
    FileLocationArray,
    FileMetaData,
    PresignedLink,
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


@handle_client_exception
async def get_download_file_presigned_link(
    session: ClientSession, file_id: str, location_id: str, user_id: UserID
) -> AnyUrl:
    if (
        not isinstance(file_id, str)
        or not isinstance(location_id, str)
        or not isinstance(user_id, int)
    ):
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are invalid",
        )
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are not allowed to be empty",
        )

    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()

        presigned_link_enveloped = Envelope[PresignedLink].parse_obj(
            await response.json()
        )
        if presigned_link_enveloped.data is None:
            raise exceptions.StorageServerIssue("Storage server is not reponding")
        return presigned_link_enveloped.data.link


@handle_client_exception
async def get_upload_file_presigned_link(
    session: ClientSession, file_id: str, location_id: str, user_id: UserID
) -> AnyUrl:
    if (
        not isinstance(file_id, str)
        or not isinstance(location_id, str)
        or not isinstance(user_id, int)
    ):
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are invalid",
        )
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are not allowed to be empty",
        )
    async with session.put(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}"},
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
    session: ClientSession, file_id: str, location_id: str, user_id: UserID
) -> Dict[str, Any]:
    if (
        not isinstance(file_id, str)
        or not isinstance(location_id, str)
        or not isinstance(user_id, int)
    ):
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are invalid",
        )
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall(
            f"invalid call: user_id '{user_id}', location_id '{location_id}', file_id '{file_id}' are not allowed to be empty",
        )
    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}/metadata",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()
        file_metadata_enveloped = Envelope[FileMetaData].parse_obj(
            await response.json()
        )
        if file_metadata_enveloped.data is None:
            raise exceptions.S3InvalidPathError(file_id)
        return file_metadata_enveloped.data.dict(by_alias=True)
