# pylint: disable=redefined-outer-name
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from typing import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_storage.application import create
from simcore_service_storage.settings import Settings

pytest_simcore_core_services_selection = ["postgres", "migration"]
pytest_simcore_ops_services_selection = ["minio", "adminer"]


@pytest.fixture
def app_settings(postgres_host_config: dict[str, str], minio_config) -> Settings:
    test_app_settings = Settings.create_from_envs()
    print(f"{test_app_settings=}")
    return test_app_settings


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable[..., int],
    app_settings: Settings,
) -> TestClient:
    app = create(app_settings)
    return event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": unused_tcp_port_factory()})
    )


async def test_simcore_s3_access(client: TestClient):
    assert client.app
    url = (
        client.app.router["get_or_create_temporary_s3_access"]
        .url_for()
        .with_query(user_id=1)
    )
    response = await client.get(f"{url}")
    await assert_status(response, web.HTTPOk)
