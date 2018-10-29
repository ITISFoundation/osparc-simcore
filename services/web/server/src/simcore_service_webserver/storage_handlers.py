from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from .login.decorators import login_required, restricted_to
from .db_models import UserRole
from servicelib.request_keys import RQT_USERID_KEY

from . import __version__

# TODO: Implement redirects with client sdk or aiohttp client

@login_required
async def get_storage_locations(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    userid = request[RQT_USERID_KEY]
    print("this is the user id", userid)

    # TODO: retrieve from db tokens

    #resp = await client.get("/v0/storage/locations/")
    #payload = await resp.json()
    #return payload

    #user_id = await authorized_userid(request)
    #async with aiohttp.ClientSession() as session:
    #    async with session.get('http/get') as resp:
    #        print(resp.status)
    #        print(await resp.text())

    locs = [ { "name": "bla", "id" : 0 }]

    envelope = {
        'error': None,
        'data': locs
        }

    return envelope


@login_required
async def get_files_metadata(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)
    # get user_id, add to query and pass to storage
    raise NotImplementedError


@login_required
async def get_file_metadata(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError


@login_required
async def update_file_meta_data(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError


@login_required
async def download_file(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError


@login_required
async def upload_file(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError


@restricted_to(UserRole.MODERATOR)
async def delete_file(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError
