# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import pytest
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_api_proxy import DockerApiProxysettings
from simcore_service_director import docker_utils
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "docker-api-proxy",
]


@pytest.fixture
def setup_docker_api_proxy(
    docker_api_proxy_settings: DockerApiProxysettings, app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "DIRECTOR_DOCKER_API_PROXY": json_dumps(
                model_dump_with_secrets(docker_api_proxy_settings, show_secrets=True)
            ),
        },
    )


async def test_docker_client(setup_docker_api_proxy: None, app: FastAPI):
    async with docker_utils.docker_client(app) as client:
        await client.images.pull("alpine:latest")
        container = await client.containers.create_or_replace(
            config={
                "Cmd": ["/bin/ash", "-c", 'echo "hello world"'],
                "Image": "alpine:latest",
            },
            name="testing",
        )
        await container.start()
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(AssertionError), stop=stop_after_delay(30), wait=wait_fixed(0.1)
        ):
            with attempt:
                logs = await container.log(stdout=True)
                assert ("".join(logs)) == "hello world\n", f"running containers {client.containers.list()}"
                await container.delete(force=True)


async def test_swarm_get_number_nodes(setup_docker_api_proxy: None, app: FastAPI):
    num_nodes = await docker_utils.swarm_get_number_nodes(app)
    assert num_nodes == 1


async def test_swarm_has_manager_nodes(setup_docker_api_proxy: None, app: FastAPI):
    assert (await docker_utils.swarm_has_manager_nodes(app)) is True


async def test_swarm_has_worker_nodes(setup_docker_api_proxy: None, app: FastAPI):
    assert (await docker_utils.swarm_has_worker_nodes(app)) is False
