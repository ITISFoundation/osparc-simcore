# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import asyncio
from typing import Callable
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.users import UserID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    unused_tcp_port_factory: Callable,
    aiohttp_client: Callable,
    api_version_prefix: str,
    mock_env_devel_environment: EnvVarsDict,
    mock_env_auto_deployer_agent: EnvVarsDict,
) -> TestClient:
    app = create_safe_application()

    MAX_DELAY_SECS_ALLOWED = 1  # secs

    async def slow_handler(request: web.Request):
        import time

        time.sleep(MAX_DELAY_SECS_ALLOWED * 1.1)
        raise web.HTTPOk()

    server_kwargs = {"port": unused_tcp_port_factory(), "host": "localhost"}

    # activates only security+restAPI sub-modules
    setup_settings(app)
    setup_security(app)
    setup_rest(app)

    app.router.add_get("/slow", slow_handler)

    cli = event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs=server_kwargs)
    )
    return cli


async def test_frontend_config(
    client: TestClient, api_version_prefix: str, mocker: MockerFixture
):
    assert client.app
    # avoids having to start database etc...
    mocker.patch(
        "simcore_service_webserver.rest._handlers.get_product_name",
        spec=True,
        return_value="osparc",
    )

    url = client.app.router["get_config"].url_for()
    assert str(url) == f"/{api_version_prefix}/config"

    response = await client.get(f"/{api_version_prefix}/config")

    data, _ = await assert_status(response, web.HTTPOk)
    assert not data["invitation_required"]


@pytest.fixture
def mock_user_logged_in(mocker: MockerFixture) -> UserID:
    user_id = 1
    # patches @login_required decorator
    # NOTE: that these tests have no database!
    mocker.patch(
        "simcore_service_webserver.login.decorators.check_authorized",
        spec=True,
        return_value=user_id,
    )
    return user_id


@pytest.fixture
async def mock_redis_client(
    client: TestClient,
    mocker: MockerFixture,
    redis_maintenance_data: dict[str, str],
) -> MagicMock:
    assert client.app

    # mocks redis response
    mock = mocker.patch(
        "simcore_service_webserver.rest._handlers.get_redis_scheduled_maintenance_client",
        spec=True,
    )
    redis_client = mock.return_value

    async def _get(hash_key):
        return redis_maintenance_data

    redis_client.get.side_effect = _get
    return redis_client


@pytest.mark.parametrize(
    "redis_maintenance_data,expected",
    [
        (None, web.HTTPNoContent),
        (
            {
                "start": "2023-01-17T14:45:00.000Z",
                "end": "2023-01-17T23:00:00.000Z",
                "reason": "Release 1.0.4",
            },
            web.HTTPOk,
        ),
    ],
)
async def test_get_scheduled_maintenance(
    client: TestClient,
    api_version_prefix: str,
    redis_maintenance_data: dict[str, str],
    expected: type[web.HTTPException],
    mock_user_logged_in: UserID,
    mock_redis_client: MagicMock,
):
    assert client.app

    url = client.app.router["get_scheduled_maintenance"].url_for()

    # test url
    assert str(url) == f"/{api_version_prefix}/scheduled_maintenance"
    response = await client.get(f"{url}")

    # test response
    data, error = await assert_status(response, expected)
    assert error is None
    if redis_maintenance_data:
        assert data == redis_maintenance_data
