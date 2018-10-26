from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from .security import authorized_userid, login_required

from . import __version__

# TODO: Implement redirects with client sdk or aiohttp client

@login_required
async def get_storage_locations(request: web.Request):
   # params, query, body = await extract_and_validate(request)

    #resp = await client.get("/v0/storage/locations")
    #payload = await resp.json()
    #return payload

    #user_id = await authorized_userid(request)
    #async with aiohttp.ClientSession() as session:
    #    async with session.get('http://httpbin.org/get') as resp:
    #        print(resp.status)
    #        print(await resp.text())

    locs = [ { "name": "bla", "id" : 0 }]

    envelope = {
        'error': None,
        'data': locs
        }

    return envelope

async def get_files_metadata(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)
    # get user_id, add to query and pass to storage
    raise NotImplementedError

async def get_file_metadata(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError

async def update_file_meta_data(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError

async def download_file(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError

async def upload_file(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError

async def delete_file(request: web.Request):
    _params, _query, _body = await extract_and_validate(request)

    # get user_id, add to query and pass to storage
    raise NotImplementedError
