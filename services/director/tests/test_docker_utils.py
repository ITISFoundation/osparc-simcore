# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint: disable=not-async-context-manager
from asyncio import sleep

import pytest

from aiodocker.exceptions import DockerError
from simcore_service_director import docker_utils


async def test_docker_client(loop):
    async with docker_utils.docker_client() as client:
        await client.images.pull("alpine:latest")
        container = await client.containers.create_or_replace(
            config={
                "Cmd": ["/bin/ash", "-c", 'echo "hello world"'],
                "Image": "alpine:latest",
            },
            name="testing",
        )
        await container.start()
        await sleep(5)
        logs = await container.log(stdout=True)
        assert (
            "".join(logs)
        ) == "hello world\n", f"running containers {client.containers.list()}"
        await container.delete(force=True)


@pytest.mark.parametrize(
    "fct",
    [
        (docker_utils.swarm_get_number_nodes),
        (docker_utils.swarm_has_manager_nodes),
        (docker_utils.swarm_has_worker_nodes),
    ],
)
async def test_swarm_method_with_no_swarm(loop, fct):
    # if this fails on your development machine run
    # `docker swarm leave --force` to leave the swarm
    with pytest.raises(DockerError):
        await fct()


async def test_swarm_get_number_nodes(loop, docker_swarm):
    num_nodes = await docker_utils.swarm_get_number_nodes()
    assert num_nodes == 1


async def test_swarm_has_manager_nodes(loop, docker_swarm):
    assert (await docker_utils.swarm_has_manager_nodes()) == True


async def test_swarm_has_worker_nodes(loop, docker_swarm):
    assert (await docker_utils.swarm_has_worker_nodes()) == False
