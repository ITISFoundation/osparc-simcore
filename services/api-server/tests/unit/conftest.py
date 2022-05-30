# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pprint import pprint
from typing import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx._transports.asgi import ASGITransport
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_api_server.core.application import init_app
from simcore_service_api_server.core.settings import ApplicationSettings

## APP & TEST CLIENT ------


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
