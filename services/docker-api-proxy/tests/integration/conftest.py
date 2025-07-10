# pylint:disable=unrecognized-options

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated

import aiodocker
import pytest
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from pydantic import Field
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.docker import (
    create_remote_docker_client_input_state,
    get_remote_docker_client,
    remote_docker_client_lifespan,
)
from settings_library.application import BaseApplicationSettings
from settings_library.docker_api_proxy import DockerApiProxysettings

pytest_plugins = [
    "pytest_simcore.docker_api_proxy",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.logging",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_services",
]


def pytest_configure(config):
    # Set asyncio_mode to "auto"
    config.option.asyncio_mode = "auto"


class ApplicationSetting(BaseApplicationSettings):
    DOCKER_API_PROXY: Annotated[
        DockerApiProxysettings,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ]


async def _settings_lifespan(app: FastAPI) -> AsyncIterator[State]:
    settings: ApplicationSetting = app.state.settings

    yield {
        **create_remote_docker_client_input_state(settings.DOCKER_API_PROXY),
    }


def _get_test_app() -> FastAPI:
    settings = ApplicationSetting.create_from_envs()

    lifespan_manager = LifespanManager()
    lifespan_manager.add(_settings_lifespan)
    lifespan_manager.add(remote_docker_client_lifespan)

    app = FastAPI(lifespan=lifespan_manager)
    app.state.settings = settings

    return app


@pytest.fixture
async def setup_docker_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[EnvVarsDict], AbstractAsyncContextManager[aiodocker.Docker]]:
    @asynccontextmanager
    async def _(env_vars: EnvVarsDict) -> AsyncIterator[aiodocker.Docker]:
        setenvs_from_dict(monkeypatch, env_vars)

        app = _get_test_app()

        async with ASGILifespanManager(app, startup_timeout=30, shutdown_timeout=30):
            yield get_remote_docker_client(app)

    return _
