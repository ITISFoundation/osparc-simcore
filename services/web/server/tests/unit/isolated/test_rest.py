# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security


@pytest.fixture
async def client(
    unused_tcp_port_factory: Callable,
    aiohttp_client: Callable[..., Awaitable[TestClient]],
    api_version_prefix: str,
    mock_webserver_service_environment: EnvVarsDict,
    mocked_db_setup_in_setup_security: MockType,
) -> TestClient:
    app = create_safe_application()

    MAX_DELAY_SECS_ALLOWED = 1  # secs

    async def slow_handler(request: web.Request):
        import time

        time.sleep(MAX_DELAY_SECS_ALLOWED * 1.1)
        raise web.HTTPOk

    server_kwargs = {"port": unused_tcp_port_factory(), "host": "localhost"}

    # activates only security+restAPI sub-modules
    setup_settings(app)
    setup_security(app)
    setup_rest(app)

    app.router.add_get("/slow", slow_handler)

    return await aiohttp_client(app, server_kwargs=server_kwargs)


async def test_frontend_config(
    client: TestClient, api_version_prefix: str, mocker: MockerFixture
):
    assert client.app
    # avoids having to start database etc...
    mocker.patch(
        "simcore_service_webserver.rest._handlers.products_web.get_product_name",
        spec=True,
        return_value="osparc",
    )

    url = client.app.router["get_config"].url_for()
    assert str(url) == f"/{api_version_prefix}/config"

    response = await client.get(f"/{api_version_prefix}/config")

    data, _ = await assert_status(response, status.HTTP_200_OK)
    assert not data["invitation_required"]


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
        (None, status.HTTP_204_NO_CONTENT),
        (
            {
                "start": "2023-01-17T14:45:00.000Z",
                "end": "2023-01-17T23:00:00.000Z",
                "reason": "Release 1.0.4",
            },
            status.HTTP_200_OK,
        ),
    ],
)
async def test_get_scheduled_maintenance(
    client: TestClient,
    api_version_prefix: str,
    redis_maintenance_data: dict[str, str],
    expected: HTTPStatus,
    mocked_login_required: None,
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
