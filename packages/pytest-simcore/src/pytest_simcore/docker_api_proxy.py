import logging

import pytest
from aiohttp import ClientSession, ClientTimeout
from pydantic import TypeAdapter
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
    async with ClientSession(timeout=ClientTimeout(1, 1, 1, 1, 1)) as client:
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
        }
    )

    await _wait_till_docker_api_proxy_is_responsive(settings)

    return settings
