from asyncio.log import logger
from contextlib import asynccontextmanager
from pprint import pformat
from typing import AsyncIterator

from aiodocker import Docker, DockerError
from models_library.docker import DockerImage


@asynccontextmanager
async def docker_client() -> AsyncIterator[Docker]:
    async with Docker("unix:///var/run/docker.sock") as docker:
        yield docker


async def pull_image(image: DockerImage) -> bool:
    async with docker_client() as docker:
        try:
            result = await docker.images.pull(image)
            logger.debug("Pull result:\n%s", pformat(result))
        except DockerError as err:
            logger.info("Could not pull image %s, because %s", image, f"{err}")
            return False

    return True


# NOTE: it is not possible to determine container usage via docker statistics
# we can monitor the docker engine for container create events, like:
#    `docker events --filter "event=create" --filter "type=container"`
# This will provide a good way to keep track of started containers, the metrics should be stored somewhere
# like in REDIS and used by each task to figure out the overall usage of the image!
