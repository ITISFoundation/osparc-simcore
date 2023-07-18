# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
from collections.abc import AsyncIterable, Awaitable, Callable
from uuid import uuid4

import pytest
import socketio
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from yarl import URL

logger = logging.getLogger(__name__)


@pytest.fixture
def client_session_id_factory() -> Callable[[], str]:
    def _create() -> str:
        return str(uuid4())

    return _create


@pytest.fixture
def socketio_url_factory(client) -> Callable[[TestClient | None], str]:
    def _create(client_override: TestClient | None = None) -> str:
        SOCKET_IO_PATH = "/socket.io/"
        return str((client_override or client).make_url(SOCKET_IO_PATH))

    return _create


@pytest.fixture
async def security_cookie_factory(
    client: TestClient,
) -> Callable[[TestClient | None], Awaitable[str]]:
    async def _create(client_override: TestClient | None = None) -> str:
        # get the cookie by calling the root entrypoint
        resp = await (client_override or client).get("/v0/")
        data, error = await assert_status(resp, web.HTTPOk)
        assert data
        assert not error

        return (
            resp.request_info.headers["Cookie"]
            if "Cookie" in resp.request_info.headers
            else ""
        )

    return _create


@pytest.fixture
async def socketio_client_factory(
    socketio_url_factory: Callable,
    security_cookie_factory: Callable,
    client_session_id_factory: Callable,
) -> AsyncIterable[
    Callable[[str | None, TestClient | None], Awaitable[socketio.AsyncClient]]
]:
    clients: list[socketio.AsyncClient] = []

    async def _connect(
        client_session_id: str | None = None, client: TestClient | None = None
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

        print(f"--> Connecting socketio client to {url} ...")
        await sio.connect(url, headers=headers, wait_timeout=10)
        assert sio.sid
        print("... connection done")
        clients.append(sio)
        return sio

    yield _connect

    # cleans up clients produce by _connect(*) calls
    for sio in clients:
        if sio.connected:
            print(f"<--Disconnecting socketio client {sio}")
            await sio.disconnect()
            await sio.wait()
            print(f"... disconnection from {sio} done.")

        assert not sio.sid
