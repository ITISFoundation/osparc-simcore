# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from copy import deepcopy
from typing import Any, Callable, Dict, Iterator
from uuid import uuid4

import pytest
from aiohttp import web
from aiohttp.client import ClientSession
from aiohttp.test_utils import TestServer
from faker import Faker
from servicelib.aiohttp.application_keys import APP_CLIENT_SESSION_KEY
from servicelib.aiohttp.client_session import (
    get_client_session,
    persistent_client_session,
)
from servicelib.json_serialization import json_dumps


@pytest.fixture
def fake_data(faker: Faker) -> Dict[str, Any]:
    data = {
        "uuid": uuid4(),
        "int": faker.pyint(),
        "float": faker.pyfloat(),
        "str": faker.pystr(),
    }
    data["object"] = deepcopy(data)
    return data


@pytest.fixture
def server(loop, aiohttp_server: Callable) -> Iterator[TestServer]:
    async def echo(request):
        got = await request.json()
        return web.json_response(data=got)

    app = web.Application()
    app.add_routes([web.post("/echo", echo)])

    app.cleanup_ctx.append(persistent_client_session)

    assert not app.get(APP_CLIENT_SESSION_KEY)

    test_server = loop.run_until_complete(aiohttp_server(app))

    assert isinstance(app[APP_CLIENT_SESSION_KEY], ClientSession)
    assert not app[APP_CLIENT_SESSION_KEY].closed

    yield test_server


async def test_get_always_the_same_client_session():
    app = web.Application()
    session = get_client_session(app)

    assert session in app.values()
    assert app[APP_CLIENT_SESSION_KEY] == session

    for _ in range(3):
        assert get_client_session(app) == session


async def test_app_client_session_json_serialize(
    server: TestServer, fake_data: Dict[str, Any]
):
    session = get_client_session(server.app)

    resp = await session.post(server.make_url("/echo"), json=fake_data)
    assert resp.status == 200

    got = await resp.json()

    expected = json.loads(json_dumps(fake_data))
    assert got == expected
