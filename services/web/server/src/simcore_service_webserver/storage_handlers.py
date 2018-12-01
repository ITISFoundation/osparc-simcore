from aiohttp import web
from yarl import URL

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_utils import extract_and_validate

from .login.decorators import login_required
from .storage_config import get_client_session, get_config


def _resolve_storage_url(request: web.Request) -> URL:
    """ Composes a new url against storage API

    """
    userid = request[RQT_USERID_KEY]
    cfg = get_config(request.app)

    # storage service API endpoint
    endpoint = URL.build(scheme='http',
                         host=cfg['host'],
                         port=cfg['port']).with_path(cfg["version"])

    BASEPATH_INDEX = 3
    # strip basepath from webserver API path (i.e. webserver api version)
    # >>> URL('http://storage:1234/v5/storage/asdf/').raw_parts[3:]
    #    ('asdf', '')
    suffix = "/".join( request.url.raw_parts[BASEPATH_INDEX:] )

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


#---------------------------------------------------------------------

@login_required
async def get_storage_locations(request: web.Request):
    payload = await _request_storage(request, 'GET')
    return payload


@login_required
async def get_files_metadata(request: web.Request):
    payload = await _request_storage(request, 'GET')
    return payload


@login_required
async def get_file_metadata(request: web.Request):
    payload = await _request_storage(request, 'GET')
    return payload


@login_required
async def update_file_meta_data(_request: web.Request):
    raise NotImplementedError
    # payload = await _request_storage(request, 'PATCH')
    # return payload


@login_required
async def download_file(request: web.Request):
    payload = await _request_storage(request, 'GET')
    return payload


@login_required
async def upload_file(request: web.Request):
    payload = await _request_storage(request, 'PUT')
    return payload

@login_required
async def delete_file(request: web.Request):
    payload = await _request_storage(request, 'DELETE')
    return payload
