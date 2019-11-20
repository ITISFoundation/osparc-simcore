# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint: disable=not-async-context-manager
import pytest
from aiodocker.exceptions import DockerError

from simcore_service_director import docker_utils


async def test_docker_client(loop):
    async with docker_utils.docker_client() as client:
        await client.images.pull("alpine:latest")
        container = await client.containers.create_or_replace(
            config={
                'Cmd': ['/bin/ash', '-c', 'echo "hello world"'],
                'Image': 'alpine:latest',
            },
            name='testing',
        )
        await container.start()
        logs = await container.log(stdout=True)
        assert (''.join(logs)) == "hello world\n"
        await container.delete(force=True)

@pytest.mark.parametrize("fct", [
    (docker_utils.swarm_get_number_nodes),
    (docker_utils.swarm_has_manager_nodes),
    (docker_utils.swarm_has_worker_nodes)
])
async def test_swarm_method_with_no_swarm(loop, fct):
    with pytest.raises(DockerError):
        await fct()

async def test_swarm_get_number_nodes(loop, docker_swarm):
    num_nodes = await docker_utils.swarm_get_number_nodes()
    assert num_nodes == 1

async def test_swarm_has_manager_nodes(loop, docker_swarm):
    assert (await docker_utils.swarm_has_manager_nodes()) == True

async def test_swarm_has_worker_nodes(loop, docker_swarm):
    assert (await docker_utils.swarm_has_worker_nodes()) == False
