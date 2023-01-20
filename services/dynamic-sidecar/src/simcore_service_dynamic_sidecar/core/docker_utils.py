import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Awaitable, Callable, Final

import aiodocker
import yaml
from aiodocker.utils import clean_filters
from models_library.basic_regex import DOCKER_GENERIC_TAG_KEY_RE
from models_library.services import RunID
from pydantic import PositiveInt
from settings_library.docker_registry import RegistrySettings

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


ProgressCB = Callable[[int, int], Awaitable[None]]
LogCB = Callable[[str], Awaitable[None]]


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
                    image,
                    registry_settings,
                    images_pulling_data,
                    progress_cb,
                    log_cb,
                )
                for image in images
            )
        )


_DOWNLOAD_RATIO: Final[float] = 0.75


async def _pull_image_with_progress(
    client: aiodocker.Docker,
    registry_settings: RegistrySettings,
    image: str,
    all_image_pulling_data: dict[str, Any],
    progress_cb: ProgressCB,
    log_cb: LogCB,
) -> None:
    # NOTE: if there is no registry_host, then there is no auth allowed,
    # which is typical for dockerhub or local images
    # NOTE: progress is such that downloading is taking 3/4 of the time,
    # Extracting 1/4
    match = DOCKER_GENERIC_TAG_KEY_RE.match(image)
    registry_host = ""
    if match:
        registry_host = match.group("registry_host")
    else:
        logger.error(
            "%s does not match typical docker image pattern, please check! Image pulling will still be attempted but may fail.",
            f"{image=}",
        )

    simplified_image_name = image.rsplit("/", maxsplit=1)[-1]
    all_image_pulling_data[image] = {}
    async for pull_progress in client.images.pull(
        image,
        stream=True,
        auth={
            "username": registry_settings.REGISTRY_USER,
            "password": registry_settings.REGISTRY_PW.get_secret_value(),
        }
        if registry_host
        else None,
    ):
        if pull_progress.get("status") == "Downloading":
            # NOTE: this takes the bulk of the time
            layer_id = pull_progress["id"]
            all_image_pulling_data[image][layer_id] = (
                _DOWNLOAD_RATIO * pull_progress["progressDetail"]["current"],
                pull_progress["progressDetail"]["total"],
            )
        elif pull_progress.get("status") == "Download complete":
            layer_id = pull_progress["id"]
            _, layer_total_size = all_image_pulling_data[image][layer_id]
            all_image_pulling_data[image][layer_id] = (
                _DOWNLOAD_RATIO * layer_total_size,
                layer_total_size,
            )
        elif pull_progress.get("status") == "Extracting":
            layer_id = pull_progress["id"]
            _, layer_total_size = all_image_pulling_data[image][layer_id]
            all_image_pulling_data[image][layer_id] = (
                _DOWNLOAD_RATIO * layer_total_size
                + (1 - _DOWNLOAD_RATIO) * pull_progress["progressDetail"]["current"],
                layer_total_size,
            )
        elif pull_progress.get("status") == "Pull complete":
            layer_id = pull_progress["id"]
            _, layer_total_size = all_image_pulling_data[image][layer_id]
            all_image_pulling_data[image][layer_id] = (
                layer_total_size,
                layer_total_size,
            )

        def _compute_sizes(
            all_images: dict[str, dict[str, tuple[int, int]]]
        ) -> tuple[int, int]:
            total_current_size = total_total_size = 0
            for layer in all_images.values():
                for current_size, total_size in layer.values():
                    total_current_size += current_size
                    total_total_size += total_size
            return (total_current_size, total_total_size)

        total_current, total_total = _compute_sizes(all_image_pulling_data)
        await progress_cb(total_current, total_total)
        await log_cb(f"pulling {simplified_image_name}: {pull_progress}...")
