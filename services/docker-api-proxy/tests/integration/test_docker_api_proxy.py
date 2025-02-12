# pylint: disable=unused-argument

import json
import sys
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import aiodocker
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from settings_library.docker_api_proxy import DockerApiProxysettings

HERE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytest_simcore_core_services_selection = [
    "docker-api-proxy",
]


async def test_unauthenticated_docker_client(
    docker_swarm: None,
    docker_api_proxy_settings: DockerApiProxysettings,
    setup_docker_client: Callable[
        [EnvVarsDict], AbstractAsyncContextManager[aiodocker.Docker]
    ],
):
    envs = {
        "DOCKER_API_PROXY_HOST": "127.0.0.1",
        "DOCKER_API_PROXY_PORT": "8014",
    }
    async with setup_docker_client(envs) as working_docker:
        info = await working_docker.system.info()
        print(json.dumps(info, indent=2))
