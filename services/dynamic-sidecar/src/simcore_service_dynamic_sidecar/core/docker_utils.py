import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator
from uuid import UUID

import aiodocker
from aiodocker.utils import clean_filters
from pydantic import BaseModel, Field

from .errors import UnexpectedDockerError, VolumeNotFoundError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def docker_client() -> AsyncGenerator[aiodocker.Docker, None]:
    docker = aiodocker.Docker()
    try:
        yield docker
    except aiodocker.exceptions.DockerError as error:
        logger.debug("An unexpected Docker error occurred", stack_info=True)
        raise UnexpectedDockerError(
            message=error.message, status=error.status
        ) from error
    finally:
        await docker.close()


class VolumeLabels(BaseModel):
    run_id: str
    source: str


class VolumeInspect(BaseModel):
    """Partial model of the data returned by 'docker volume inspect'"""

    created_at: datetime = Field(..., alias="CreatedAt")
    labels: VolumeLabels = Field(..., alias="Labels")
    mountpoint: Path = Field(..., alias="Mountpoint")
    name: str = Field(alias="Name")


async def get_volume_by_label(label: str, run_id: UUID) -> VolumeInspect:
    async with docker_client() as docker:
        filters = clean_filters({"label": [f"source={label}", f"run_id={run_id}"]})
        data = await docker._query_json(  # pylint: disable=protected-access
            "volumes", method="GET", params={"filters": filters}
        )
        volumes = data["Volumes"]
        logger.debug("volumes query for %s %s", f"{label=}", f"{volumes=}")
        if len(volumes) != 1:
            raise VolumeNotFoundError(label, run_id, volumes)
        return VolumeInspect.parse_obj(volumes[0])
