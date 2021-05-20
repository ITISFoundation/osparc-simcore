# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Callable, Optional
from uuid import uuid4

import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from yarl import URL


@pytest.fixture()
def socketio_url_factory(client) -> Callable:
    def create_url(client_override: Optional[TestClient] = None) -> str:
        SOCKET_IO_PATH = "/socket.io/"
        return str((client_override or client).make_url(SOCKET_IO_PATH))

    yield create_url


@pytest.fixture()
async def security_cookie_factory(client) -> Callable:
    async def creator(client_override: Optional[TestClient] = None) -> str:
        # get the cookie by calling the root entrypoint
        resp = await (client_override or client).get("/v0/")
        data, error = await assert_status(resp, web.HTTPOk)
        assert data
        assert not error

        cookie = (
            resp.request_info.headers["Cookie"]
            if "Cookie" in resp.request_info.headers
            else ""
        )
        return cookie

    yield creator


@pytest.fixture()
async def socketio_client_factory(
    socketio_url_factory: Callable, security_cookie_factory: Callable
) -> Callable[[str, Optional[TestClient]], socketio.AsyncClient]:
    clients = []

    async def connect(
        client_session_id: str, client: Optional[TestClient] = None
    ) -> socketio.AsyncClient:
        sio = socketio.AsyncClient(ssl_verify=False)
        # enginio 3.10.0 introduced ssl verification
        url = str(
            URL(socketio_url_factory(client)).with_query(
                {"client_session_id": client_session_id}
            )
        )
        headers = {}
        cookie = await security_cookie_factory(client)
        if cookie:
            # WARNING: engineio fails with empty cookies. Expects "key=value"
            headers.update({"Cookie": cookie})

        await sio.connect(url, headers=headers)
        assert sio.sid
        clients.append(sio)
        return sio

    yield connect

    for sio in clients:
        await sio.disconnect()
        assert not sio.sid


@pytest.fixture()
def client_session_id_factory() -> Callable[[], str]:
    def create() -> str:
        return str(uuid4())

    return create
