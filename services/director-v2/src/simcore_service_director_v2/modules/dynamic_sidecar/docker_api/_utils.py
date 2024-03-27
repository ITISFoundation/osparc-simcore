from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiodocker

from ..errors import GenericDockerError


@asynccontextmanager
async def docker_client() -> AsyncIterator[aiodocker.docker.Docker]:
    client = None
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError as e:
        message = "Unexpected error from docker client"
        raise GenericDockerError(message, e) from e
    finally:
        if client is not None:
            await client.close()
