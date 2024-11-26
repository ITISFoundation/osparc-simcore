import logging
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Any

import aiodocker
import yaml
from aiodocker.containers import DockerContainer
from aiodocker.utils import clean_filters
from models_library.docker import DockerGenericTag
from models_library.generated_models.docker_rest_api import ContainerState
from models_library.generated_models.docker_rest_api import Status2 as ContainerStatus
from models_library.services import RunID
from pydantic import PositiveInt
from servicelib.utils import logged_gather
from starlette import status as http_status

from .errors import UnexpectedDockerError, VolumeNotFoundError

_logger = logging.getLogger(__name__)


_ACCEPTED_CONTAINER_STATUSES: set[str] = {
    ContainerStatus.created,
    ContainerStatus.running,
}


@asynccontextmanager
async def docker_client() -> AsyncGenerator[aiodocker.Docker, None]:
    docker = aiodocker.Docker()
    try:
        yield docker
    except aiodocker.exceptions.DockerError as error:
        _logger.debug("An unexpected Docker error occurred", exc_info=True)
        raise UnexpectedDockerError(
            message=error.message, status_code=error.status
        ) from error
    finally:
        await docker.close()


async def get_volume_by_label(label: str, run_id: RunID) -> dict[str, Any]:
    async with docker_client() as docker:
        filters = {"label": [f"source={label}", f"run_id={run_id}"]}
        params = {"filters": clean_filters(filters)}
        data = await docker._query_json(  # pylint: disable=protected-access  # noqa: SLF001
            "volumes", method="GET", params=params
        )
        volumes = data["Volumes"]
        _logger.debug("volumes query for label=%s volumes=%s", label, volumes)
        if len(volumes) != 1:
            raise VolumeNotFoundError(
                volume_count=len(volumes),
                source_label=label,
                run_id=run_id,
                volume_names=" ".join(v.get("Name", "UNKNOWN") for v in volumes),
                status_code=http_status.HTTP_404_NOT_FOUND,
            )
        volume_details: dict[str, Any] = volumes[0]
        return volume_details


async def _get_container(
    docker: aiodocker.Docker, container_name: str
) -> DockerContainer | None:
    try:
        return await docker.containers.get(container_name)
    except aiodocker.DockerError as e:
        if e.status == http_status.HTTP_404_NOT_FOUND:
            return None
        raise


async def _get_containers_inspect_from_names(
    container_names: list[str],
) -> dict[str, DockerContainer | None]:
    # NOTE: returned objects have their associated Docker client session closed
    if len(container_names) == 0:
        return {}

    containers_inspect: dict[str, DockerContainer | None] = {
        x: None for x in container_names
    }

    async with docker_client() as docker:
        docker_containers: list[DockerContainer | None] = await logged_gather(
            *(
                _get_container(docker, container_name)
                for container_name in container_names
            )
        )
        for docker_container in docker_containers:
            if docker_container is None:
                continue

            stripped_name = docker_container["Name"].lstrip("/")
            if stripped_name in containers_inspect:
                containers_inspect[stripped_name] = docker_container

    return containers_inspect


async def get_container_states(
    container_names: list[str],
) -> dict[str, ContainerState | None]:
    """if a container is not found it's status is None"""
    containers_inspect = await _get_containers_inspect_from_names(container_names)
    return {
        k: None if v is None else ContainerState(**v["State"])
        for k, v in containers_inspect.items()
    }


def are_all_containers_in_expected_states(
    states: Iterable[ContainerState | None],
) -> bool:
    return all(
        s is not None and s.status in _ACCEPTED_CONTAINER_STATUSES for s in states
    )


async def get_containers_count_from_names(
    container_names: list[str],
) -> PositiveInt:
    # this one could handle the error
    return len(await _get_containers_inspect_from_names(container_names))


def get_docker_service_images(compose_spec_yaml: str) -> set[DockerGenericTag]:
    docker_compose_spec = yaml.safe_load(compose_spec_yaml)
    return {
        DockerGenericTag(service_data["image"])
        for service_data in docker_compose_spec["services"].values()
    }
