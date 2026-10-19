# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint: disable=not-async-context-manager
from asyncio import sleep

from simcore_service_director import docker_utils


async def test_docker_client():
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
        assert ("".join(logs)) == "hello world\n", f"running containers {client.containers.list()}"
        await container.delete(force=True)


async def test_swarm_get_number_nodes(docker_swarm: None):
    num_nodes = await docker_utils.swarm_get_number_nodes()
    assert num_nodes == 1
