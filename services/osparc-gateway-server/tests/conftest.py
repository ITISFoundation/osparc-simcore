# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable

import aiodocker
import osparc_gateway_server
import pytest
from faker import Faker
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_plugins = ["pytest_simcore.repository_paths", "pytest_simcore.docker_swarm"]


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
WILDCARD = "services/osparc-gateway-server/README.md"
ROOT = Path("/")


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(osparc_gateway_server.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture
async def async_docker_client() -> AsyncIterator[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
async def docker_network(
    async_docker_client: aiodocker.Docker, faker: Faker
) -> AsyncIterator[Callable[..., Awaitable[dict[str, Any]]]]:
    networks = []

    async def _network_creator(**network_config_kwargs) -> dict[str, Any]:
        network = await async_docker_client.networks.create(
            config={"Name": faker.uuid4(), "Driver": "overlay"} | network_config_kwargs
        )
        assert network
        print(f"--> created network {network=}")
        networks.append(network)
        return await network.show()

    yield _network_creator

    # wait until all networks are really gone
    async def _wait_for_network_deletion(network: aiodocker.docker.DockerNetwork):
        network_name = (await network.show())["Name"]
        await network.delete()
        async for attempt in AsyncRetrying(
            reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)
        ):
            with attempt:
                print(f"<-- waiting for network '{network_name}' deletion...")
                list_of_network_names = [
                    n["Name"] for n in await async_docker_client.networks.list()
                ]
                assert network_name not in list_of_network_names
            print(f"<-- network '{network_name}' deleted")

    print(f"<-- removing all networks {networks=}")
    await asyncio.gather(*[_wait_for_network_deletion(network) for network in networks])
