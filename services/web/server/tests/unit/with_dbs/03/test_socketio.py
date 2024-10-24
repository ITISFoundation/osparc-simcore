# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import pytest
import socketio
from aiohttp.test_utils import TestClient, TestServer
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_postgres_database.models.users import UserRole
from simcore_service_webserver.application_settings import ApplicationSettings
from yarl import URL


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    overrides = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_GROUPS": "0",
            "WEBSERVER_META_MODELING": "0",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_PROJECTS": "null",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "1",  # <--- activate only sockets
            "WEBSERVER_STORAGE": "null",
            "WEBSERVER_STUDIES_DISPATCHER": "null",
            "WEBSERVER_TAGS": "0",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_DIRECTOR_V2": "null",
            "WEBSERVER_CATALOG": "null",
            "WEBSERVER_REDIS": "null",
            "WEBSERVER_SCICRUNCH": "null",
            "WEBSERVER_VERSION_CONTROL": "0",
            "WEBSERVER_WALLETS": "0",
        },
    )

    print(ApplicationSettings.create_from_envs().model_dump_json(indent=1))

    return app_environment | overrides


@pytest.mark.skip(
    reason="Pending https://github.com/ITISFoundation/osparc-simcore/issues/5332"
)
@pytest.mark.parametrize("user_role", (UserRole.USER,))
async def test_socketio_session_client_to_server(
    logged_user: UserInfoDict,
    client: TestClient,
    user_role: UserRole,
    mocker: MockerFixture,
):

    assert client.app
    assert client.server
    assert isinstance(client.server, TestServer)

    # makes sure it is logged-in
    response = await client.get("/v0/me")
    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert data["login"] == logged_user["email"]

    # emulates front-end client
    sio = socketio.AsyncClient(http_session=client.session)
    client_session_id = "abcd"

    url = URL.build(
        scheme=client.server.scheme,
        host=client.server.host,
        port=client.server.port,
        query={"client_session_id": client_session_id},
    )
    await sio.connect(f"{url}", wait_timeout=1000)
    assert sio.sid

    # client -> server
    message_ack = mocker.MagicMock()
    await sio.emit("client_heartbeat", callback=message_ack)

    message_ack.assert_called_once()

    await sio.disconnect()
