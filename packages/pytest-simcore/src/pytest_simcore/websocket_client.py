# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
import socketio
from yarl import URL

from servicelib.rest_responses import unwrap_envelope


@pytest.fixture()
async def security_cookie(loop, client) -> str:
    # get the cookie by calling the root entrypoint
    resp = await client.get("/v0/")
    payload = await resp.json()
    assert resp.status == 200, str(payload)
    data, error = unwrap_envelope(payload)
    assert data
    assert not error

    cookie = ""
    if "Cookie" in resp.request_info.headers:
        cookie = resp.request_info.headers["Cookie"]
    yield cookie


@pytest.fixture()
async def socketio_url(loop, client) -> str:
    SOCKET_IO_PATH = "/socket.io/"
    return str(client.make_url(SOCKET_IO_PATH))


@pytest.fixture()
async def socketio_client(
    socketio_url: str, security_cookie: str
) -> socketio.AsyncClient:
    clients = []

    async def connect(client_session_id) -> socketio.AsyncClient:
        sio = socketio.AsyncClient(
            ssl_verify=False
        )  # enginio 3.10.0 introduced ssl verification
        url = str(
            URL(socketio_url).with_query({"client_session_id": client_session_id})
        )

        headers = {}
        if security_cookie:
            # WARNING: engineio fails with empty cookies. Expects "key=value"
            headers.update({"Cookie": security_cookie})

        await sio.connect(url, headers=headers)
        assert sio.sid
        clients.append(sio)
        return sio

    yield connect

    for sio in clients:
        await sio.disconnect()
        assert not sio.sid
