import datetime
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import lru_cache, wraps
from json import JSONDecodeError
from typing import Any, TypeAlias
from urllib.parse import quote

from aiohttp import ClientResponse, ClientSession
from aiohttp import client as aiohttp_client_module
from aiohttp import web
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
from tenacity import RetryCallState
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_exponential

from . import exceptions
from .settings import NodePortsSettings

_logger = logging.getLogger(__name__)


RequestContextManager: TypeAlias = (
    aiohttp_client_module._RequestContextManager  # pylint: disable=protected-access # noqa: SLF001
)


def handle_client_exception(handler: Callable) -> Callable[..., Awaitable[Any]]:
    @wraps(handler)
    async def wrapped(*args, **kwargs):
        try:
            return await handler(*args, **kwargs)
        except ClientResponseError as err:
            if err.status == web.HTTPNotFound.status_code:
                msg = kwargs.get("file_id", "unknown file id")
                raise exceptions.S3InvalidPathError(msg) from err
            if err.status == web.HTTPUnprocessableEntity.status_code:
                msg = f"Invalid call to storage: {err.message}"
                raise exceptions.StorageInvalidCall(msg) from err
            if (
                web.HTTPInternalServerError.status_code
                > err.status
                >= web.HTTPBadRequest.status_code
            ):
                raise exceptions.StorageInvalidCall(err.message) from err
            if err.status > web.HTTPInternalServerError.status_code:
                raise exceptions.StorageServerIssue(err.message) from err
        except ClientConnectionError as err:
            msg = f"{err}"
            raise exceptions.StorageServerIssue(msg) from err
        except JSONDecodeError as err:
            msg = f"{err}"
            raise exceptions.StorageServerIssue(msg) from err

    return wrapped


@lru_cache
def _base_url() -> str:
    settings = NodePortsSettings.create_from_envs()
    base_url: str = settings.NODE_PORTS_STORAGE.api_base_url
    return base_url


def _after_log(log: logging.Logger) -> Callable[[RetryCallState], None]:
    def log_it(retry_state: RetryCallState) -> None:
        assert retry_state.outcome  # nosec
        e = retry_state.outcome.exception()
        log.error(
            "Request timed-out after %s attempts with an unexpected error: '%s'",
            retry_state.attempt_number,
            f"{e=}",
        )

    return log_it


def _session_method(
    session: ClientSession, method: str, url: str, **kwargs
) -> RequestContextManager:
    return session.request(method, url, **kwargs)


@asynccontextmanager
async def retry_request(
    session: ClientSession,
    method: str,
    url: str,
    *,
    expected_status: int,
    give_up_after: datetime.timedelta = datetime.timedelta(seconds=30),
    **kwargs,
) -> AsyncIterator[ClientResponse]:
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(give_up_after.total_seconds()),
        wait=wait_exponential(min=1),
        retry=retry_if_exception_type(ClientConnectionError),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
        after=_after_log(_logger),
        reraise=True,
    ):
        with attempt:
            async with _session_method(session, method, url, **kwargs) as response:
                if response.status != expected_status:
                    # this is a more precise raise_for_status()
                    response.release()
                    raise ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"Received {response.status} but was expecting {expected_status=}",
                        headers=response.headers,
                    )

                yield response


@handle_client_exception
async def get_storage_locations(
    *, session: ClientSession, user_id: UserID
) -> FileLocationArray:
    async with retry_request(
        session,
        "GET",
        f"{_base_url()}/locations",
        expected_status=web.HTTPOk.status_code,
        params={"user_id": f"{user_id}"},
    ) as response:
        locations_enveloped = Envelope[FileLocationArray].parse_obj(
            await response.json()
        )
        if locations_enveloped.data is None:
            msg = "Storage server is not responding"
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
    async with retry_request(
        session,
        "GET",
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        expected_status=web.HTTPOk.status_code,
        params={"user_id": f"{user_id}", "link_type": link_type.value},
    ) as response:
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
        query_params["sha256_checksum"] = f"{sha256_checksum}"
    async with retry_request(
        session,
        "PUT",
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        expected_status=web.HTTPOk.status_code,
        params=query_params,
    ) as response:
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
    async with retry_request(
        session,
        "GET",
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}/metadata",
        expected_status=web.HTTPOk.status_code,
        params={"user_id": f"{user_id}"},
    ) as response:
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
    async with retry_request(
        session,
        "GET",
        f"{_base_url()}/locations/{location_id}/files/metadata",
        expected_status=web.HTTPOk.status_code,
        params={"user_id": f"{user_id}", "uuid_filter": uuid_filter},
    ) as resp:
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
    async with retry_request(
        session,
        "DELETE",
        f"{_base_url()}/locations/{location_id}/files/{quote(file_id, safe='')}",
        expected_status=web.HTTPNoContent.status_code,
        params={"user_id": f"{user_id}"},
    ):
        ...
