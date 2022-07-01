""" Handlers exposed by storage subsystem

    Mostly resolves and redirect to storage API
"""
import logging
import urllib
import urllib.parse
from typing import Any, Optional, Union

from aiohttp import ClientResponse, web
from models_library.api_schemas_storage import (
    FileLocationArray,
    FileMetaDataGet,
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    PresignedLink,
    UploadedPart,
)
from models_library.generics import Envelope
from models_library.projects_nodes_io import LocationID, StorageFileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.rest_responses import create_data_response, unwrap_envelope
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.request_keys import RQT_USERID_KEY
from yarl import URL

from .login.decorators import login_required
from .security_decorators import permission_required
from .storage_settings import StorageSettings, get_plugin_settings

log = logging.getLogger(__name__)


def _get_base_storage_url(app: web.Application) -> URL:
    settings: StorageSettings = get_plugin_settings(app)

    # storage service API endpoint
    return URL(settings.base_url)


def _get_storage_vtag(app: web.Application) -> str:
    settings: StorageSettings = get_plugin_settings(app)
    return settings.STORAGE_VTAG


def _resolve_storage_url(request: web.Request) -> URL:
    """Composes a new url against storage API"""
    userid = request[RQT_USERID_KEY]

    # storage service API endpoint
    endpoint = _get_base_storage_url(request.app)

    BASEPATH_INDEX = 3
    # strip basepath from webserver API path (i.e. webserver api version)
    # >>> URL('http://storage:1234/v5/storage/asdf/').raw_parts[3:]
    #    ('asdf', '')
    suffix = "/".join(request.url.raw_parts[BASEPATH_INDEX:])

    # TODO: check request.query to storage! unsafe!?
    url = (endpoint / suffix).with_query(request.query).update_query(user_id=userid)
    return url


Payload = Any
StatusCode = int


async def _request_storage(
    request: web.Request, method: str, **kwargs
) -> tuple[Payload, StatusCode]:
    # NOTE: this extrac/validate stuff fails with bodies...
    if not request.has_body:
        await extract_and_validate(request)

    url = _resolve_storage_url(request)
    # _token_data, _token_secret = _get_token_key_and_secret(request)

    body = None
    if request.can_read_body:
        body = await request.json()

    session = get_client_session(request.app)
    async with session.request(
        method.upper(), url, ssl=False, json=body, **kwargs
    ) as resp:
        payload = await resp.json()
        return (payload, resp.status)


def _unresolve_storage_url(request: web.Request, storage_url: AnyUrl) -> AnyUrl:
    assert storage_url.path  # nosec
    prefix = f"/{_get_storage_vtag(request.app)}"
    converted_url = request.url.with_path(
        f"/v0/storage{storage_url.path.removeprefix(prefix)}"
    )
    return parse_obj_as(AnyUrl, f"{converted_url}")


async def safe_unwrap(
    resp: ClientResponse,
) -> tuple[Optional[Union[dict[str, Any], list[dict[str, Any]]]], Optional[dict]]:
    resp.raise_for_status()

    payload = await resp.json()
    if not isinstance(payload, dict):
        raise web.HTTPException(reason=f"Did not receive a dict: '{payload}'")

    data, error = unwrap_envelope(payload)

    return data, error


def extract_link(data: Optional[dict]) -> str:
    if data is None or "link" not in data:
        raise web.HTTPException(reason=f"No url found in response: '{data}'")

    return data["link"]


# ---------------------------------------------------------------------


@login_required
@permission_required("storage.files.*")
async def get_storage_locations(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "GET")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def get_datasets_metadata(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "GET")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def get_files_metadata(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "GET")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def get_files_metadata_dataset(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "GET")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def get_file_metadata(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "GET")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def download_file(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "GET")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def upload_file(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "PUT")
    data, _ = unwrap_envelope(payload)
    file_upload_schema = FileUploadSchema.parse_obj(data)
    file_upload_schema.links.complete_upload = _unresolve_storage_url(
        request, file_upload_schema.links.complete_upload
    )
    file_upload_schema.links.abort_upload = _unresolve_storage_url(
        request, file_upload_schema.links.abort_upload
    )
    return create_data_response(jsonable_encoder(file_upload_schema), status=status)


@login_required
@permission_required("storage.files.*")
async def complete_upload_file(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "POST")
    data, _ = unwrap_envelope(payload)
    file_upload_complete = FileUploadCompleteResponse.parse_obj(data)
    file_upload_complete.links.state = _unresolve_storage_url(
        request, file_upload_complete.links.state
    )
    return create_data_response(jsonable_encoder(file_upload_complete), status=status)


@login_required
@permission_required("storages.files.*")
async def abort_upload_file(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "POST")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def is_completed_upload_file(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "POST")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.*")
async def delete_file(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "DELETE")
    return create_data_response(payload, status=status)


@login_required
@permission_required("storage.files.sync")
async def synchronise_meta_data_table(request: web.Request) -> web.Response:
    payload, status = await _request_storage(request, "POST")
    return create_data_response(payload, status=status)


async def get_storage_locations_for_user(
    app: web.Application, user_id: UserID
) -> FileLocationArray:
    session = get_client_session(app)

    url: URL = _get_base_storage_url(app) / "locations"
    params = dict(user_id=user_id)
    async with session.get(url, ssl=False, params=params) as resp:
        resp.raise_for_status()
        envelope = Envelope[FileLocationArray].parse_obj(await resp.json())
        assert envelope.data  # nosec
        return envelope.data


async def get_project_files_metadata(
    app: web.Application, location_id: LocationID, uuid_filter: str, user_id: UserID
) -> list[FileMetaDataGet]:
    session = get_client_session(app)

    url: URL = (
        _get_base_storage_url(app)
        / "locations"
        / f"{location_id}"
        / "files"
        / "metadata"
    )
    params = dict(user_id=user_id, uuid_filter=uuid_filter)
    async with session.get(url, ssl=False, params=params) as resp:
        resp.raise_for_status()
        envelope = Envelope[list[FileMetaDataGet]].parse_obj(await resp.json())
        assert envelope.data  # nosec
        return envelope.data


async def get_file_download_url(
    app: web.Application,
    location_id: LocationID,
    file_id: StorageFileID,
    user_id: UserID,
) -> AnyUrl:
    session = get_client_session(app)

    url: URL = (
        _get_base_storage_url(app)
        / "locations"
        / f"{location_id}"
        / "files"
        / urllib.parse.quote(file_id, safe="")
    )
    params = dict(user_id=user_id)
    async with session.get(url, ssl=False, params=params) as resp:
        resp.raise_for_status()
        envelope = Envelope[PresignedLink].parse_obj(await resp.json())
        assert envelope.data  # nosec
        return envelope.data.link


async def get_file_upload_url(
    app: web.Application,
    location_id: LocationID,
    file_id: StorageFileID,
    user_id: UserID,
) -> str:
    session = get_client_session(app)

    url: URL = (
        _get_base_storage_url(app)
        / "locations"
        / f"{location_id}"
        / "files"
        / urllib.parse.quote(file_id, safe="")
    )
    params = dict(user_id=user_id, file_size=0)
    async with session.put(url, ssl=False, params=params) as resp:
        resp.raise_for_status()
        envelope = Envelope[FileUploadSchema].parse_obj(await resp.json())
        assert envelope.data  # nosec
        assert len(envelope.data.urls) == 1  # nosec
        return envelope.data.urls[0]


async def complete_file_upload(
    app: web.Application,
    location_id: str,
    file_id: str,
    user_id: UserID,
    parts: list[UploadedPart],
) -> AnyUrl:
    session = get_client_session(app)

    url: URL = (
        _get_base_storage_url(app)
        / "locations"
        / location_id
        / "files"
        / f"{urllib.parse.quote(file_id, safe='')}:complete"
    )
    params = dict(user_id=user_id)
    async with session.post(
        url,
        ssl=False,
        params=params,
        json=FileUploadCompletionBody.construct(parts=parts),
    ) as resp:
        resp.raise_for_status()
        envelope = Envelope[FileUploadCompleteResponse].parse_obj(await resp.json())
        assert envelope.data  # nosec
        return envelope.data.links.state
