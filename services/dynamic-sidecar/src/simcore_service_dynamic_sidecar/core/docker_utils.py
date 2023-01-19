import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import aiodocker
import yaml
from aiodocker.utils import clean_filters
from models_library.services import RunID
from pydantic import PositiveInt

from .errors import UnexpectedDockerError, VolumeNotFoundError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def docker_client() -> AsyncGenerator[aiodocker.Docker, None]:
    docker = aiodocker.Docker()
    try:
        yield docker
    except aiodocker.exceptions.DockerError as error:
        logger.debug("An unexpected Docker error occurred", exc_info=True)
        raise UnexpectedDockerError(
            message=error.message, status=error.status
        ) from error
    finally:
        await docker.close()


async def get_volume_by_label(label: str, run_id: RunID) -> dict[str, Any]:
    async with docker_client() as docker:
        filters = {"label": [f"source={label}", f"run_id={run_id}"]}
        params = {"filters": clean_filters(filters)}
        data = await docker._query_json(  # pylint: disable=protected-access
            "volumes", method="GET", params=params
        )
        volumes = data["Volumes"]
        logger.debug(  # pylint: disable=logging-fstring-interpolation
            f"volumes query for {label=} {volumes=}"
        )
        if len(volumes) != 1:
            raise VolumeNotFoundError(label, run_id, volumes)
        volume_details = volumes[0]
        return volume_details  # type: ignore


async def get_running_containers_count_from_names(
    container_names: list[str],
) -> PositiveInt:
    if len(container_names) == 0:
        return 0

    async with docker_client() as docker:
        filters = clean_filters({"name": container_names})
        containers = await docker.containers.list(all=True, filters=filters)
        return len(containers)


def get_docker_service_images(compose_spec_yaml: str) -> set[str]:
    docker_compose_spec = yaml.safe_load(compose_spec_yaml)
    return {
        service_data["image"]
        for service_data in docker_compose_spec["services"].values()
    }
