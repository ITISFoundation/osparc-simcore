# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pprint import pprint
from typing import AsyncIterator, Iterator

import aiohttp.test_utils
import httpx
import pytest
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from faker import Faker
from fastapi import FastAPI
from httpx._transports.asgi import ASGITransport
from moto.server import ThreadedMotoServer
from pydantic import HttpUrl, parse_obj_as
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from requests.auth import HTTPBasicAuth
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import ApplicationSettings

## APP + SYNC/ASYNC CLIENTS --------------------------------------------------


@pytest.fixture
def patched_light_app_environ(
    patched_default_app_environ: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    """Config that disables many plugins e.g. database or tracing"""

    env_vars = {}
    env_vars.update(patched_default_app_environ)

    pprint(list(ApplicationSettings.schema()["properties"].keys()))
    # [
    # 'SC_BOOT_MODE',
    # 'LOG_LEVEL',
    # 'API_SERVER_POSTGRES',
    # 'API_SERVER_WEBSERVER',
    # 'API_SERVER_CATALOG',
    # 'API_SERVER_STORAGE',
    # 'API_SERVER_DIRECTOR_V2',
    # 'API_SERVER_TRACING',
    # 'API_SERVER_DEV_FEATURES_ENABLED',
    # 'API_SERVER_REMOTE_DEBUG_PORT'
    # ]
    #
    env_vars.update(
        {
            "WEBSERVER_HOST": "webserver",
            "WEBSERVER_SESSION_SECRET_KEY": Fernet.generate_key().decode("utf-8"),
            "API_SERVER_POSTGRES": "null",
            "API_SERVER_TRACING": "null",
            "LOG_LEVEL": "debug",
            "SC_BOOT_MODE": "production",
        }
    )
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture
def app(patched_light_app_environ: EnvVarsDict) -> FastAPI:
    """Inits app on a light environment"""
    the_app = init_app()
    return the_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    #
    # Prefer this client instead of fastapi.testclient.TestClient
    #
    async with LifespanManager(app):
        # needed for app to trigger start/stop event handlers
        async with httpx.AsyncClient(
            app=app,
            base_url="http://api.testserver.io",
            headers={"Content-Type": "application/json"},
        ) as client:

            assert isinstance(client._transport, ASGITransport)
            # rewires location test's app to client.app
            setattr(client, "app", client._transport.app)

            yield client


## MOCKED Repositories --------------------------------------------------


@pytest.fixture
def auth(mocker, app: FastAPI, faker: Faker) -> HTTPBasicAuth:
    """
    Auth mocking repositories and db engine (i.e. does not require db up)

    """
    # mock engine if db was not init
    if app.state.settings.API_SERVER_POSTGRES is None:

        engine = mocker.Mock()
        engine.minsize = 1
        engine.size = 10
        engine.freesize = 3
        engine.maxsize = 10
        app.state.engine = engine

    # patch authentication entry in repo
    faker_user_id = faker.pyint()

    # NOTE: here, instead of using the database, we patch repositories interface
    mocker.patch(
        "simcore_service_api_server.db.repositories.api_keys.ApiKeysRepository.get_user_id",
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_user_id",
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_email_from_user_id",
        return_value=faker.email(),
    )
    return HTTPBasicAuth(faker.word(), faker.password())


## MOCKED S3 service --------------------------------------------------


@pytest.fixture
def mocked_s3_server_url() -> Iterator[HttpUrl]:
    """
    For download links, the in-memory moto.mock_s3() does not suffice since
    we need an http entrypoint
    """
    # http://docs.getmoto.org/en/latest/docs/server_mode.html#start-within-python
    server = ThreadedMotoServer(
        ip_address=get_localhost_ip(), port=aiohttp.test_utils.unused_port()
    )

    # pylint: disable=protected-access
    endpoint_url = parse_obj_as(HttpUrl, f"http://{server._ip_address}:{server._port}")

    print(f"--> started mock S3 server on {endpoint_url}")
    server.start()

    yield endpoint_url

    server.stop()
    print(f"<-- stopped mock S3 server on {endpoint_url}")
