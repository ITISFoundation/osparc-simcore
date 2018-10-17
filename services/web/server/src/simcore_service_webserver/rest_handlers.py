""" Basic diagnostic handles to the rest API for operations


"""
import attr
from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from .rest_models import FakeType, HealthCheckType


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

    # output
    return attr.asdict(data)



async def check_action(request: web.Request):
    # input
    params, query, body = await extract_and_validate(request)

    assert params
    assert body

    action = params['action']
    data = FakeType(
        path_value= action ,
        query_value= query['data'] if query else None,
        # TODO to_dict of string
        # TODO: analyze how schemas models are deserialized!
        body_value= 'under construction', )

    if action == 'fail':
        raise ValueError("some randome failure")

    return attr.asdict(data)
