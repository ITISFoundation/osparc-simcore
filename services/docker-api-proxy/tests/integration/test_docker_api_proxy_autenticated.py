# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import aiodocker
import pytest
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from settings_library.docker_api_proxy import DockerApiProxysettings
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

pytest_simcore_core_services_selection = [
    "docker-api-proxy",
]

_HERE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture
def authentication_proxy_compose_path() -> Path:
    compose_spec_path = _HERE / "autentication-proxy-docker-compose.yaml"
    assert compose_spec_path.exists()
    return compose_spec_path


@pytest.fixture
def caddy_file() -> str:
    # NOTE: the basicauth encrypeted credentials are `asd:asd``
    return """
:9999 {
    handle {
        basicauth {
            asd $2a$14$slb.GSUwFUX4jPOMoYTmKePjH.2UPJBkLmTPT5RmOfn38seYld1nu
        }
        reverse_proxy http://docker-api-proxy:8888 {
            health_uri /version
        }
    }
}
    """


@pytest.fixture
def authentication_proxy(
    docker_swarm: None,
    docker_api_proxy_settings: DockerApiProxysettings,
    caddy_file: str,
    authentication_proxy_compose_path: Path,
) -> Iterator[None]:

    stack_name = "with-auth"
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "stack",
            "deploy",
            "-c",
            authentication_proxy_compose_path,
            stack_name,
        ],
        check=True,
        env={"CADDY_FILE": caddy_file},
    )

    yield

    subprocess.run(  # noqa: S603
        ["docker", "stack", "rm", stack_name], check=True  # noqa: S607
    )


async def test_with_correct_credentials(
    authentication_proxy: None,
    setup_docker_client: Callable[
        [EnvVarsDict], AbstractAsyncContextManager[aiodocker.Docker]
    ],
):
    envs = {
        "DOCKER_API_PROXY_HOST": "127.0.0.1",
        "DOCKER_API_PROXY_PORT": "9999",
        "DOCKER_API_PROXY_USER": "asd",
        "DOCKER_API_PROXY_PASSWORD": "asd",
    }
    async with setup_docker_client(envs) as working_docker:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1), stop=stop_after_delay(10), reraise=True
        ):
            with attempt:
                info = await working_docker.system.info()
                print(json.dumps(info, indent=2))


async def test_wrong_credentials(
    authentication_proxy: None,
    setup_docker_client: Callable[
        [EnvVarsDict], AbstractAsyncContextManager[aiodocker.Docker]
    ],
):
    envs = {
        "DOCKER_API_PROXY_HOST": "127.0.0.1",
        "DOCKER_API_PROXY_PORT": "9999",
        "DOCKER_API_PROXY_USER": "wrong",
        "DOCKER_API_PROXY_PASSWORD": "wrong",
    }
    async with setup_docker_client(envs) as failing_docker_client:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1), stop=stop_after_delay(10), reraise=True
        ):
            with attempt:  # noqa: SIM117
                with pytest.raises(aiodocker.exceptions.DockerError, match="401"):
                    await failing_docker_client.system.info()
