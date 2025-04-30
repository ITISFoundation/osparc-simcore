# pylint: disable=unused-argument

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import aiodocker
import pytest
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from servicelib.aiohttp import status
from settings_library.docker_api_proxy import DockerApiProxysettings

pytest_simcore_core_services_selection = [
    "docker-api-proxy",
]


async def test_authenticated_docker_client(
    docker_swarm: None,
    docker_api_proxy_settings: DockerApiProxysettings,
    setup_docker_client: Callable[
        [EnvVarsDict], AbstractAsyncContextManager[aiodocker.Docker]
    ],
):
    envs = {
        "DOCKER_API_PROXY_HOST": "127.0.0.1",
        "DOCKER_API_PROXY_PORT": "8014",
        "DOCKER_API_PROXY_USER": docker_api_proxy_settings.DOCKER_API_PROXY_USER,
        "DOCKER_API_PROXY_PASSWORD": docker_api_proxy_settings.DOCKER_API_PROXY_PASSWORD.get_secret_value(),
    }
    async with setup_docker_client(envs) as working_docker:
        info = await working_docker.system.info()
        print(json.dumps(info, indent=2))


@pytest.mark.parametrize(
    "user, password",
    [
        ("wrong", "wrong"),
        ("wrong", "admin"),
    ],
)
async def test_unauthenticated_docker_client(
    docker_swarm: None,
    docker_api_proxy_settings: DockerApiProxysettings,
    setup_docker_client: Callable[
        [EnvVarsDict], AbstractAsyncContextManager[aiodocker.Docker]
    ],
    user: str,
    password: str,
):
    envs = {
        "DOCKER_API_PROXY_HOST": "127.0.0.1",
        "DOCKER_API_PROXY_PORT": "8014",
        "DOCKER_API_PROXY_USER": user,
        "DOCKER_API_PROXY_PASSWORD": password,
    }
    async with setup_docker_client(envs) as working_docker:
        with pytest.raises(aiodocker.exceptions.DockerError) as exc:
            await working_docker.system.info()
        assert exc.value.status == status.HTTP_401_UNAUTHORIZED
