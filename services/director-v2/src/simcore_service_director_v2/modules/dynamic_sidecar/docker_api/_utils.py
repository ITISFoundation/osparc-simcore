from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiodocker

from ..errors import GenericDockerError


@asynccontextmanager
async def docker_client() -> AsyncIterator[aiodocker.docker.Docker]:
    client = None
    try:
        client = aiodocker.Docker()
        yield client
    except aiodocker.exceptions.DockerError as e:
        raise GenericDockerError(msg=f"{e.message}", original_exception=e) from e
    finally:
        if client is not None:
            await client.close()
