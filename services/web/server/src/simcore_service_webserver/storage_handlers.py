""" Handlers exposed by storage subsystem

    Mostly resolves and redirect to storage API
"""
import logging
import urllib
from typing import Any, Dict, List, Optional, Tuple

from aiohttp import web
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_responses import unwrap_envelope
from servicelib.rest_utils import extract_and_validate
from yarl import URL

from .login.decorators import login_required
from .security_api import check_permission
from .storage_config import get_client_session, get_storage_config

log = logging.getLogger(__name__)


def _get_base_storage_url(app: web.Application) -> URL:
    cfg = get_storage_config(app)

    # storage service API endpoint
    return URL.build(scheme="http", host=cfg["host"], port=cfg["port"]).with_path(
        cfg["version"]
    )


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


async def _request_storage(request: web.Request, method: str):
    await extract_and_validate(request)

    url = _resolve_storage_url(request)
    # _token_data, _token_secret = _get_token_key_and_secret(request)

    body = None
    if request.can_read_body:
        body = await request.json()

    session = get_client_session(request.app)
    async with session.request(method.upper(), url, ssl=False, json=body) as resp:
        payload = await resp.json()
        return payload


async def safe_unwrap(resp: web.Response) -> Tuple[Optional[Dict], Optional[Dict]]:
    if resp.status != 200:
        body = await resp.text()
        raise web.HTTPException(reason=f"Unexpected response: '{body}'")

    payload = await resp.json()
    if not isinstance(payload, dict):
        raise web.HTTPException(reason=f"Did not receive a dict: '{payload}'")

    data, error = unwrap_envelope(payload)

    return data, error


def extract_link(data: Optional[Dict]) -> str:
    if data is None or "link" not in data:
        raise web.HTTPException(reason=f"No url found in response: '{data}'")

    return data["link"]


# ---------------------------------------------------------------------


@login_required
async def get_storage_locations(request: web.Request):
    await check_permission(request, "storage.locations.*")
    payload = await _request_storage(request, "GET")
    return payload


@login_required
async def get_datasets_metadata(request: web.Request):
    await check_permission(request, "storage.files.*")
    payload = await _request_storage(request, "GET")
    return payload


@login_required
async def get_files_metadata(request: web.Request):
    await check_permission(request, "storage.files.*")
    payload = await _request_storage(request, "GET")
    return payload


@login_required
async def get_files_metadata_dataset(request: web.Request):
    await check_permission(request, "storage.files.*")
    payload = await _request_storage(request, "GET")
    return payload


@login_required
async def get_file_metadata(request: web.Request):
    await check_permission(request, "storage.files.*")
    payload = await _request_storage(request, "GET")
    return payload


@login_required
async def update_file_meta_data(request: web.Request):
    await check_permission(request, "storage.files.*")
    raise NotImplementedError
    # payload = await _request_storage(request, 'PATCH' or 'PUT'???) See projects
    # return payload


@login_required
async def download_file(request: web.Request):
    await check_permission(request, "storage.files.*")
    payload = await _request_storage(request, "GET")
    return payload


@login_required
async def upload_file(request: web.Request):
    await check_permission(request, "storage.files.*")
    payload = await _request_storage(request, "PUT")
    return payload


@login_required
async def delete_file(request: web.Request):
    await check_permission(request, "storage.files.*")
    payload = await _request_storage(request, "DELETE")
    return payload


async def get_project_files_metadata(
    app: web.Application, location_id: str, uuid_filter: str, user_id: int
) -> List[Dict[str, Any]]:
    session = get_client_session(app)

    url: URL = (
        _get_base_storage_url(app) / "locations" / location_id / "files" / "metadata"
    )
    params = dict(user_id=user_id, uuid_filter=uuid_filter)
    async with session.get(url, ssl=False, params=params) as resp:
        data, _ = await safe_unwrap(resp)

        if data is None:
            raise web.HTTPException(reason=f"No url found in response: '{data}'")
        if not isinstance(data, list):
            raise web.HTTPException(
                reason=f"No list payload received as data: '{data}'"
            )

        return data


async def get_file_download_url(
    app: web.Application, location_id: str, fileId: str, user_id: int
) -> str:
    session = get_client_session(app)

    url: URL = (
        _get_base_storage_url(app)
        / "locations"
        / location_id
        / "files"
        / urllib.parse.quote(fileId, safe="")
    )
    params = dict(user_id=user_id)
    async with session.get(url, ssl=False, params=params) as resp:
        data, _ = await safe_unwrap(resp)
        return extract_link(data)


async def get_file_upload_url(
    app: web.Application, location_id: str, fileId: str, user_id: int
) -> str:
    session = get_client_session(app)

    url: URL = (
        _get_base_storage_url(app)
        / "locations"
        / location_id
        / "files"
        / urllib.parse.quote(fileId, safe="")
    )
    params = dict(user_id=user_id)
    async with session.put(url, ssl=False, params=params) as resp:
        data, _ = await safe_unwrap(resp)
        return extract_link(data)
