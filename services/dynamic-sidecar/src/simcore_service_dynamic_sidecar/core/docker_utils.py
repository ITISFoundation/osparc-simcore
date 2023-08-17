import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Final, TypedDict

import aiodocker
import yaml
from aiodocker.containers import DockerContainer
from aiodocker.utils import clean_filters
from models_library.basic_regex import DOCKER_GENERIC_TAG_KEY_RE
from models_library.generated_models.docker_rest_api import ContainerState
from models_library.generated_models.docker_rest_api import Status2 as ContainerStatus
from models_library.services import RunID
from pydantic import PositiveInt, parse_obj_as
from servicelib.logging_utils import log_catch
from servicelib.utils import logged_gather
from settings_library.docker_registry import RegistrySettings
from starlette import status

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
            message=error.message, status=error.status
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
            raise VolumeNotFoundError(label, run_id, volumes)
        volume_details: dict[str, Any] = volumes[0]
        return volume_details


async def _get_container(
    docker: aiodocker.Docker, container_name: str
) -> DockerContainer | None:
    try:
        return await docker.containers.get(container_name)
    except aiodocker.DockerError as e:
        if e.status == status.HTTP_404_NOT_FOUND:
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
        s is not None and s.Status in _ACCEPTED_CONTAINER_STATUSES for s in states
    )


async def get_containers_count_from_names(
    container_names: list[str],
) -> PositiveInt:
    return len(await _get_containers_inspect_from_names(container_names))


def get_docker_service_images(compose_spec_yaml: str) -> set[str]:
    docker_compose_spec = yaml.safe_load(compose_spec_yaml)
    return {
        service_data["image"]
        for service_data in docker_compose_spec["services"].values()
    }


ProgressCB = Callable[[int, int], Awaitable[None]]
LogLevel = int
LogCB = Callable[[str, LogLevel], Awaitable[None]]


async def pull_images(
    images: set[str],
    registry_settings: RegistrySettings,
    progress_cb: ProgressCB,
    log_cb: LogCB,
) -> None:
    images_pulling_data: dict[str, dict[str, tuple[int, int]]] = {}
    async with docker_client() as docker:
        await asyncio.gather(
            *(
                _pull_image_with_progress(
                    docker,
                    registry_settings,
                    image,
                    images_pulling_data,
                    progress_cb,
                    log_cb,
                )
                for image in images
            )
        )


#
# HELPERS
#
_DOWNLOAD_RATIO: Final[float] = 0.75

LayerId = str
_LayersInfoDict = dict[LayerId, tuple[int, int]]
ImageName = str
_ImagesInfoDict = dict[ImageName, _LayersInfoDict]


class _ProgressDetailDict(TypedDict, total=True):
    current: int
    total: int


class _DockerProgressDict(TypedDict, total=False):
    status: str
    progressDetail: _ProgressDetailDict
    progress: str
    id: str


class _TargetPullStatus(str, Enum):
    # They contain 'progressDetail'
    DOWNLOADING = "Downloading"
    DOWNLOAD_COMPLETE = "Download complete"
    EXTRACTING = "Extracting"
    PULL_COMPLETE = "Pull complete"


def _parse_docker_pull_progress(
    docker_pull_progress: _DockerProgressDict, image_pulling_data: _LayersInfoDict
) -> bool:
    # Example of docker_pull_progress with status in _TargetPullStatus
    # {'status': 'Pulling fs layer', 'progressDetail': {}, 'id': '6e3729cf69e0'}
    # {'status': 'Downloading', 'progressDetail': {'current': 309633, 'total': 30428708}, 'progress': '[>  ]  309.6kB/30.43MB', 'id': '6e3729cf69e0'}
    #
    # Examples of docker_pull_progress with status NOT in _TargetPullStatus
    # {'status': 'Digest: sha256:27cb6e6ccef575a4698b66f5de06c7ecd61589132d5a91d098f7f3f9285415a9'}
    # {'status': 'Status: Downloaded newer image for ubuntu:latest'}

    status: str | None = docker_pull_progress.get("status")

    if status in list(_TargetPullStatus):
        assert "id" in docker_pull_progress  # nosec
        assert "progressDetail" in docker_pull_progress  # nosec

        layer_id: LayerId = docker_pull_progress["id"]
        # inits (read/write order is not guaranteed)
        image_pulling_data.setdefault(layer_id, (0, 0))

        if status == _TargetPullStatus.DOWNLOADING:
            # writes
            image_pulling_data[layer_id] = (
                round(
                    _DOWNLOAD_RATIO * docker_pull_progress["progressDetail"]["current"]
                ),
                docker_pull_progress["progressDetail"]["total"],
            )
        elif status == _TargetPullStatus.DOWNLOAD_COMPLETE:
            # reads
            _, layer_total_size = image_pulling_data[layer_id]
            # writes
            image_pulling_data[layer_id] = (
                round(_DOWNLOAD_RATIO * layer_total_size),
                layer_total_size,
            )
        elif status == _TargetPullStatus.EXTRACTING:
            # reads
            _, layer_total_size = image_pulling_data[layer_id]

            # writes
            image_pulling_data[layer_id] = (
                round(
                    _DOWNLOAD_RATIO * layer_total_size
                    + (1 - _DOWNLOAD_RATIO)
                    * docker_pull_progress["progressDetail"]["current"]
                ),
                layer_total_size,
            )
        elif status == _TargetPullStatus.PULL_COMPLETE:
            # reads
            _, layer_total_size = image_pulling_data[layer_id]
            # writes
            image_pulling_data[layer_id] = (
                layer_total_size,
                layer_total_size,
            )
        return True

    return False  # no pull progress logged


def _compute_sizes(all_images: _ImagesInfoDict) -> tuple[int, int]:
    total_current_size = total_total_size = 0
    for layer in all_images.values():
        for current_size, total_size in layer.values():
            total_current_size += current_size
            total_total_size += total_size
    return (total_current_size, total_total_size)


async def _pull_image_with_progress(
    client: aiodocker.Docker,
    registry_settings: RegistrySettings,
    image_name: str,
    all_image_pulling_data: dict[str, Any],
    progress_cb: ProgressCB,
    log_cb: LogCB,
) -> None:
    # NOTE: if there is no registry_host, then there is no auth allowed,
    # which is typical for dockerhub or local images
    # NOTE: progress is such that downloading is taking 3/4 of the time,
    # Extracting 1/4
    match = DOCKER_GENERIC_TAG_KEY_RE.match(image_name)
    registry_host = ""
    if match:
        registry_host = match.group("registry_host")
    else:
        _logger.error(
            "%s does not match typical docker image pattern, please check! Image pulling will still be attempted but may fail.",
            f"{image_name=}",
        )

    shorter_image_name: Final[str] = image_name.rsplit("/", maxsplit=1)[-1]
    all_image_pulling_data[image_name] = {}
    async for pull_progress in client.images.pull(
        image_name,
        stream=True,
        auth={
            "username": registry_settings.REGISTRY_USER,
            "password": registry_settings.REGISTRY_PW.get_secret_value(),
        }
        if registry_host
        else None,
    ):
        with log_catch(_logger, reraise=False):
            if _parse_docker_pull_progress(
                parse_obj_as(_DockerProgressDict, pull_progress),
                all_image_pulling_data[image_name],
            ):
                total_current, total_total = _compute_sizes(all_image_pulling_data)
                await progress_cb(total_current, total_total)

            await log_cb(
                f"pulling {shorter_image_name}: {pull_progress}...", logging.DEBUG
            )
