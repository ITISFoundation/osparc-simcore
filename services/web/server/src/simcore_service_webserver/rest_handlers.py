""" Basic diagnostic handles to the rest API for operations


"""
from aiohttp import web

from servicelib.rest_utils import extract_and_validate, body_to_dict

from . import __version__


async def check_health(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    out = {
        'name':__name__.split('.')[0],
        'version': __version__,
        'status': 'SERVICE_RUNNING',
        'api_version': __version__
    }

    return out


async def check_action(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert body, "body %s" % body

    if params['action'] == 'fail':
        raise ValueError("some randome failure")


    # echo's input
    out = {
        "path_value" : params.get('action'),
        "query_value": query.get('data'),
        "body_value" : body_to_dict(body)
    }

    return out
