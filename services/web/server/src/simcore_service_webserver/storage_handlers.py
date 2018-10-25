from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from . import __version__


async def get_storage_locations(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert not params, "params %s" % params
    assert not query, "query %s" % query
    assert not body, "body %s" % body

    locs = [ { "name": "bla", "id" : 0 }]

    envelope = {
        'error': None,
        'data': locs
        }

    return envelope
