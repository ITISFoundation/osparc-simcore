# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
from typing import Any, AsyncIterator, Awaitable, Callable

import aiodocker
import pytest
from _host_helpers import get_this_computer_ip
from faker import Faker
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture
async def sidecar_computational_shared_volume(
    faker: Faker,
    docker_volume: Callable[[str], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    volume = await docker_volume(faker.pystr())
    return volume


@pytest.fixture
def computational_sidecar_mounted_folder() -> str:
    return "/comp_shared_folder"


@pytest.fixture
def sidecar_envs(
    computational_sidecar_mounted_folder: str,
    sidecar_computational_shared_volume: dict[str, Any],
) -> dict[str, str]:
    envs = {
        "SIDECAR_COMP_SERVICES_SHARED_FOLDER": f"{computational_sidecar_mounted_folder}",
        "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME": f"{sidecar_computational_shared_volume['Name']}",
    }
    return envs


@pytest.fixture
def sidecar_mounts(
    sidecar_computational_shared_volume: dict[str, Any],
    computational_sidecar_mounted_folder: str,
) -> list[dict[str, Any]]:
    mounts = [  # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
            "ReadOnly": True,
        },
        # the sidecar computational data must be mounted
        {
            "Source": sidecar_computational_shared_volume["Name"],
            "Target": computational_sidecar_mounted_folder,
            "Type": "volume",
            "ReadOnly": False,
        },
    ]
    return mounts


@pytest.fixture
async def create_docker_service(
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    services = []

    async def service_creator(**service_kwargs) -> dict[str, Any]:
        service = await async_docker_client.services.create(**service_kwargs)
        assert service
        assert "ID" in service
        services.append(service["ID"])
        return await async_docker_client.services.inspect(service["ID"])

    yield service_creator
    # cleanup
    await asyncio.gather(*[async_docker_client.services.delete(s) for s in services])


async def _wait_for_service_to_be_ready(
    docker_client: aiodocker.Docker, service_name: str
):
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)
    ):
        with attempt:
            tasks_list = await docker_client.tasks.list(
                filters={"service": service_name}
            )
            tasks_current_state = [t["Status"]["State"] for t in tasks_list]
            print(f"--> {service_name} service task states are {tasks_current_state=}")
            num_running = sum(current == "running" for current in tasks_current_state)
            assert num_running == 1
            print(f"--> {service_name} is running now")


@pytest.mark.parametrize(
    "image_name",
    [
        "itisfoundation/dask-sidecar:master-github-latest",
    ],
)
async def test_computational_sidecar_properly_start_stop(
    docker_swarm: None,
    sidecar_computational_shared_volume: dict[str, Any],
    async_docker_client: aiodocker.Docker,
    image_name: str,
    sidecar_envs: dict[str, str],
    sidecar_mounts: list[dict[str, Any]],
    create_docker_service: Callable[..., Awaitable[dict[str, Any]]],
):
    scheduler_service = await create_docker_service(
        task_template={
            "ContainerSpec": {
                "Image": image_name,
                "Env": sidecar_envs | {"DASK_START_AS_SCHEDULER": "1"},
                "Init": True,
                "Mounts": sidecar_mounts,
            }
        },
        endpoint_spec={"Ports": [{"PublishedPort": 8786, "TargetPort": 8786}]},
        name="pytest_dask_scheduler",
    )
    await _wait_for_service_to_be_ready(
        async_docker_client, scheduler_service["Spec"]["Name"]
    )
    sidecar_service = await create_docker_service(
        task_template={
            "ContainerSpec": {
                "Image": image_name,
                "Env": sidecar_envs
                | {"DASK_SCHEDULER_URL": f"tcp://{get_this_computer_ip()}:8786"},
                "Init": True,
                "Mounts": sidecar_mounts,
            }
        },
        name="pytest_dask_sidecar",
    )
    await _wait_for_service_to_be_ready(
        async_docker_client, sidecar_service["Spec"]["Name"]
    )
