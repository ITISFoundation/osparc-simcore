""" Handles to the rest API diagnostic operations


"""
import attr
from aiohttp import web

from .rest_utils import FakeType, HealthCheckType, extract_and_validate


async def check_health(request: web.Request):
    # input
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not body
    assert not query

    # business logic
    # TODO: implement
    data = HealthCheckType(
        name='simcore-director-service',
        status='SERVICE_RUNNING',
        api_version= '0.1.0-dev+NJuzzD9S',
        version='0.1.0-dev+N127Mfv9H')
    error = None

    # output
    return web.json_response({
        'data': attr.asdict(data),
        'error': error,
        })


async def check_action(request: web.Request):
    # input
    params, query, body = await extract_and_validate(request)

    assert params
    assert body

    action = params['action']
    data = FakeType(
        path_value=action,
        query_value=query,
        # TODO to_dict of string
        # TODO: analyze how schemas models are deserialized!
        body_value= 'under construction', )

    if action == 'fail':
        raise ValueError("some randome failure")

    enveloped = {
        'data': attr.asdict(data),
        'error': None,
    }

    # output
    return web.json_response(data=enveloped)
