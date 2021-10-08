import warnings
from functools import wraps
from json import JSONDecodeError
from typing import Any, Callable, Dict, List
from urllib.parse import quote

from aiohttp import ClientSession, ClientTimeout
from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from models_library.generics import DataEnveloped
from models_library.users import UserID
from pydantic.main import BaseModel
from pydantic.networks import AnyUrl

from ..config.http_clients import client_request_settings
from . import config, exceptions


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
            )  # type: ignore
        )
        self.is_owned = self.active_session is not session

    async def __aenter__(self):
        return self.active_session

    async def __aexit__(self, exc_type, exc, tb):
        if self.is_owned:
            warnings.warn(
                "Optional session is not recommended, pass instead controled session (e.g. from app[APP_CLIENT_SESSION_KEY])",
                category=DeprecationWarning,
            )
            await self.active_session.close()


class FileLocation(BaseModel):
    name: str
    id: int


class FileLocationsArray(BaseModel):
    __root__: List[FileLocation]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]


class PresignedLink(BaseModel):
    link: AnyUrl


FileLocationsArrayEnveloped = DataEnveloped[FileLocationsArray]
PresignedLinkEnveloped = DataEnveloped[PresignedLink]
FileMetadataEnveloped = DataEnveloped[Dict[str, Any]]


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
) -> FileLocationsArray:
    if not isinstance(user_id, int) or user_id is None:
        raise exceptions.StorageInvalidCall("invalid call!")

    async with session.get(
        f"{_base_url()}/locations", params={"user_id": f"{user_id}"}
    ) as response:
        response.raise_for_status()
        locations_enveloped = FileLocationsArrayEnveloped.parse_obj(
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
        raise exceptions.StorageInvalidCall("invalid call!")
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall("invalid call!")

    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()

        presigned_link_enveloped = PresignedLinkEnveloped.parse_obj(
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
        raise exceptions.StorageInvalidCall("invalid call!")
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall("invalid call!")
    async with session.put(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()

        presigned_link_enveloped = PresignedLinkEnveloped.parse_obj(
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
        raise exceptions.StorageInvalidCall("invalid call!")
    if file_id is None or location_id is None or user_id is None:
        raise exceptions.StorageInvalidCall("invalid call!")
    async with session.get(
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}/metadata",
        params={"user_id": f"{user_id}"},
    ) as response:
        response.raise_for_status()

        file_metadata_enveloped = FileMetadataEnveloped.parse_obj(await response.json())
        if file_metadata_enveloped.data is None:
            raise exceptions.StorageServerIssue("Storage server is not reponding")
        return file_metadata_enveloped.data
