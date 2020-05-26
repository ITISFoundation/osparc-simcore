import logging

import aiodocker
from asyncio_extras import async_contextmanager

log = logging.getLogger(__name__)


@async_contextmanager
async def docker_client() -> aiodocker.docker.Docker:
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError:
        log.exception(msg="Unexpected error with docker client")
        raise
    finally:
        await client.close()


async def swarm_get_number_nodes() -> int:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        nodes = await client.nodes.list()
        return len(nodes)


async def swarm_has_manager_nodes() -> bool:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        nodes = await client.nodes.list(filters={"role": "manager"})
        if nodes:
            return True
        return False


async def swarm_has_worker_nodes() -> bool:
    async with docker_client() as client:  # pylint: disable=not-async-context-manager
        nodes = await client.nodes.list(filters={"role": "worker"})
        if nodes:
            return True
        return False
