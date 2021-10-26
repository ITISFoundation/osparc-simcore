# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import AsyncIterable, Awaitable, Callable, Iterable, Optional
from uuid import uuid4

import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from yarl import URL


@pytest.fixture()
def client_session_id_factory() -> Callable[[], str]:
    def create() -> str:
        # NOTE:
        return str(uuid4())

    return create


@pytest.fixture()
def socketio_url_factory(client) -> Iterable[Callable[[Optional[TestClient]], str]]:
    def create_url(client_override: Optional[TestClient] = None) -> str:
        SOCKET_IO_PATH = "/socket.io/"
        return str((client_override or client).make_url(SOCKET_IO_PATH))

    yield create_url


@pytest.fixture()
async def security_cookie_factory(
    client: TestClient,
) -> AsyncIterable[Callable[[Optional[TestClient]], Awaitable[str]]]:
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
    socketio_url_factory: Callable,
    security_cookie_factory: Callable,
    client_session_id_factory: Callable,
) -> AsyncIterable[
    Callable[[Optional[str], Optional[TestClient]], Awaitable[socketio.AsyncClient]]
]:
    clients = []

    async def connect(
        client_session_id: Optional[str] = None, client: Optional[TestClient] = None
    ) -> socketio.AsyncClient:

        if client_session_id is None:
            client_session_id = client_session_id_factory()

        sio = socketio.AsyncClient(ssl_verify=False)
        # enginio 3.10.0 introduced ssl verification
        assert client_session_id
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
        if sio.connected:
            await sio.disconnect()
        assert not sio.sid
