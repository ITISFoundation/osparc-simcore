import logging
from collections.abc import Callable
from contextlib import AsyncExitStack

import aiodocker
import pytest
from aiohttp import BasicAuth, ClientSession, ClientTimeout
from fastapi import FastAPI
from pydantic import TypeAdapter
from pytest_mock.plugin import MockerFixture
from settings_library.docker_api_proxy import DockerApiProxysettings
from tenacity import before_sleep_log, retry, stop_after_delay, wait_fixed

from .helpers.docker import get_service_published_port
from .helpers.host import get_localhost_ip
from .helpers.typing_env import EnvVarsDict

_logger = logging.getLogger(__name__)


@retry(
    wait=wait_fixed(1),
    stop=stop_after_delay(10),
    before_sleep=before_sleep_log(_logger, logging.INFO),
    reraise=True,
)
async def _wait_till_docker_api_proxy_is_responsive(
    settings: DockerApiProxysettings,
) -> None:
    async with ClientSession(
        timeout=ClientTimeout(total=1),
        auth=BasicAuth(
            settings.DOCKER_API_PROXY_USER,
            settings.DOCKER_API_PROXY_PASSWORD.get_secret_value(),
        ),
    ) as client:
        response = await client.get(f"{settings.base_url}/version")
        assert response.status == 200, await response.text()


@pytest.fixture
async def docker_api_proxy_settings(
    docker_stack: dict, env_vars_for_docker_compose: EnvVarsDict
) -> DockerApiProxysettings:
    """Returns the settings of a redis service that is up and responsive"""

    prefix = env_vars_for_docker_compose["SWARM_STACK_NAME"]
    assert f"{prefix}_docker-api-proxy" in docker_stack["services"]

    published_port = get_service_published_port(
        "docker-api-proxy", int(env_vars_for_docker_compose["DOCKER_API_PROXY_PORT"])
    )

    settings = TypeAdapter(DockerApiProxysettings).validate_python(
        {
            "DOCKER_API_PROXY_HOST": get_localhost_ip(),
            "DOCKER_API_PROXY_PORT": published_port,
            "DOCKER_API_PROXY_USER": env_vars_for_docker_compose["DOCKER_API_PROXY_USER"],
            "DOCKER_API_PROXY_PASSWORD": env_vars_for_docker_compose["DOCKER_API_PROXY_PASSWORD"],
        }
    )

    await _wait_till_docker_api_proxy_is_responsive(settings)

    return settings


@pytest.fixture
async def mock_setup_remote_docker_client(mocker: MockerFixture) -> Callable[[str], None]:
    def _(target_setup_to_replace: str) -> None:
        def _setup(app: FastAPI, settings: DockerApiProxysettings) -> None:
            _ = settings
            exit_stack = AsyncExitStack()

            async def on_startup() -> None:
                app.state.remote_docker_client = await exit_stack.enter_async_context(aiodocker.Docker())

            async def on_shutdown() -> None:
                await exit_stack.aclose()

            app.add_event_handler("startup", on_startup)
            app.add_event_handler("shutdown", on_shutdown)

        mocker.patch(target_setup_to_replace, new=_setup)

    return _
