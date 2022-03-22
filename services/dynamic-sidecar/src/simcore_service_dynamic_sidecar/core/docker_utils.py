import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

import aiodocker
from aiodocker.utils import clean_filters
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


@asynccontextmanager
async def docker_client() -> AsyncGenerator[aiodocker.Docker, None]:
    docker = aiodocker.Docker()
    try:
        yield docker
    except aiodocker.exceptions.DockerError as error:
        logger.debug("An unexpected Docker error occurred", stack_info=True)
        raise HTTPException(error.status, detail=error.message) from error
    finally:
        await docker.close()


async def get_volume_by_label(label: str) -> Dict[str, Any]:
    """queries and returns the request of this thing"""
    async with docker_client() as docker:
        filters = {"label": [f"source={label}"]}
        params = {"filters": clean_filters(filters)}
        data = await docker._query_json(  # pylint: disable=protected-access
            "volumes", method="GET", params=params
        )
        volumes = data["Volumes"]
        logger.debug(  # pylint: disable=logging-fstring-interpolation
            f"volumes query for {label=} {volumes=}"
        )
        if len(volumes) != 1:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Could not find desired volume, query returned {volumes}",
            )
        volume_details = volumes[0]
        return volume_details  # type: ignore
