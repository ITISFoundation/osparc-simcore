""" Handlers exposed by storage subsystem

    Mostly resolves and redirect to storage API
"""
import logging
from typing import Any, Final

from aiohttp import ClientResponse, ClientTimeout, web
from models_library.api_schemas_storage import (
    FileUploadCompleteResponse,
    FileUploadSchema,
)
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import AnyUrl, parse_obj_as
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.rest_responses import create_data_response, unwrap_envelope
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.common_headers import X_FORWARDED_PROTO
from servicelib.request_keys import RQT_USERID_KEY
from yarl import URL

from ..login.decorators import login_required
from ..security.decorators import permission_required
from .settings import StorageSettings, get_plugin_settings

log = logging.getLogger(__name__)


def _get_base_storage_url(app: web.Application) -> URL:
    settings: StorageSettings = get_plugin_settings(app)

    # storage service API endpoint
    return URL(settings.base_url)


def _get_storage_vtag(app: web.Application) -> str:
    settings: StorageSettings = get_plugin_settings(app)
    storage_vtag: str = settings.STORAGE_VTAG
    return storage_vtag


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
    ).with_scheme(request.headers.get(X_FORWARDED_PROTO, request.url.scheme))
    converted_url_: AnyUrl = parse_obj_as(AnyUrl, f"{converted_url}")
    return converted_url_


async def safe_unwrap(
    resp: ClientResponse,
) -> tuple[dict[str, Any] | list[dict[str, Any]] | None, dict | None]:
    resp.raise_for_status()

    payload = await resp.json()
    if not isinstance(payload, dict):
        raise web.HTTPException(reason=f"Did not receive a dict: '{payload}'")

    data, error = unwrap_envelope(payload)

    return data, error


def extract_link(data: dict | None) -> str:
    if data is None or "link" not in data:
        raise web.HTTPException(reason=f"No url found in response: '{data}'")

    return f"{data['link']}"


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


_LIST_ALL_DATASETS_TIMEOUT_S: Final[int] = 60


@login_required
@permission_required("storage.files.*")
async def get_files_metadata_dataset(request: web.Request) -> web.Response:
    payload, status = await _request_storage(
        request,
        "GET",
        timeout=ClientTimeout(total=_LIST_ALL_DATASETS_TIMEOUT_S),
    )
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
@permission_required("storage.files.*")
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
