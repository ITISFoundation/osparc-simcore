# pylint:disable=unrecognized-options

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated

import aiodocker
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic import Field
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.docker import (
    get_lifespan_remote_docker_client,
    get_remote_docker_client,
)
from servicelib.fastapi.lifespan_utils import combine_lfiespan_context_managers
from settings_library.application import BaseApplicationSettings
from settings_library.docker_api_proxy import DockerApiProxysettings

pytest_plugins = [
    "pytest_simcore.docker_api_proxy",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_services",
]


def pytest_configure(config):
    # Set asyncio_mode to "auto"
    config.option.asyncio_mode = "auto"


def _get_test_app() -> FastAPI:
    class ApplicationSetting(BaseApplicationSettings):
        DOCKER_API_PROXY: Annotated[
            DockerApiProxysettings,
            Field(json_schema_extra={"auto_default_from_env": True}),
        ]

    app = FastAPI(
        lifespan=combine_lfiespan_context_managers(
            get_lifespan_remote_docker_client("DOCKER_API_PROXY")
        )
    )
    app.state.settings = ApplicationSetting.create_from_envs()

    return app


@pytest.fixture
async def setup_docker_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[EnvVarsDict], AbstractAsyncContextManager[aiodocker.Docker]]:
    @asynccontextmanager
    async def _(env_vars: EnvVarsDict) -> AsyncIterator[aiodocker.Docker]:
        setenvs_from_dict(monkeypatch, env_vars)

        app = _get_test_app()

        async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
            yield get_remote_docker_client(app)

    return _
