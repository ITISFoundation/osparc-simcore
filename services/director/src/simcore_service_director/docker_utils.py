import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiodocker

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def docker_client() -> AsyncIterator[aiodocker.docker.Docker]:
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError:
        _logger.exception(msg="Unexpected error with docker client")
        raise
    finally:
        await client.close()


async def swarm_get_number_nodes() -> int:
    async with docker_client() as client:
        nodes = await client.nodes.list()
        return len(nodes)
