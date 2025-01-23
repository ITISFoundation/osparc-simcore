# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import aiodocker
import pytest
from pydantic import TypeAdapter
from pytest_simcore.helpers.host import get_localhost_ip
from servicelib.docker_utils import get_remote_docker_client
from settings_library.docker_api_proxy import DockerApiProxysettings
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

HERE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture
def localhost_ip() -> str:
    return get_localhost_ip()


@pytest.fixture
def local_compose_path() -> Path:
    compose_spec_path = HERE / "secured-proxy-docker-compose.yaml"
    assert compose_spec_path.exists()
    return compose_spec_path


@pytest.fixture
def deploy_local_spec(
    docker_swarm: None, localhost_ip: str, local_compose_path: Path
) -> Iterator[None]:
    stack_name = "with-auth"
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "stack",
            "deploy",
            "-c",
            f"{local_compose_path}",
            stack_name,
        ],
        check=True,
        env={
            "IMAGE_NAME": "local/docker-api-proxy:production",
            "LOCALHOST_IP": f"{localhost_ip}",
            "USER_CREDENTIALS": "asd:$2y$05$c/GIJWuHO36H./0V1Pxj9.rDNHYZcFOFctBWsuKeGgoHKR6hGrLWi",
        },
    )

    yield
    subprocess.run(  # noqa: S603
        ["docker", "stack", "rm", stack_name], check=True  # noqa: S607
    )


async def test_with_autnentication(deploy_local_spec: None, localhost_ip: str):

    # epect ok
    docker_api_proxy_settings = TypeAdapter(DockerApiProxysettings).validate_python(
        {
            "DOCKER_API_PROXY_HOST": f"{localhost_ip}.nip.io",
            "DOCKER_API_PROXY_PORT": 9999,
            "DOCKER_API_PROXY_USER": "asd",
            "DOCKER_API_PROXY_PASSWORD": "asd",
        }
    )

    working_docker = await get_remote_docker_client(docker_api_proxy_settings)

    async with working_docker:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1), stop=stop_after_delay(20), reraise=True
        ):
            with attempt:
                info = await working_docker.system.info()
                print(json.dumps(info, indent=2))

    # worng credentils
    docker_api_proxy_settings = TypeAdapter(DockerApiProxysettings).validate_python(
        {
            "DOCKER_API_PROXY_HOST": f"{localhost_ip}.nip.io",
            "DOCKER_API_PROXY_PORT": 9999,
            "DOCKER_API_PROXY_USER": "wrong",
            "DOCKER_API_PROXY_PASSWORD": "wrong",
        }
    )
    failing_docker_client = await get_remote_docker_client(docker_api_proxy_settings)
    async with failing_docker_client:
        with pytest.raises(aiodocker.exceptions.DockerError, match="401"):
            await failing_docker_client.system.info()
