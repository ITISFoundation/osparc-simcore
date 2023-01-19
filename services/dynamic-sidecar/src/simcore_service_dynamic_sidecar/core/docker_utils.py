import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Final

import aiodocker
import yaml
from aiodocker.utils import clean_filters
from models_library.services import RunID
from pydantic import ByteSize, PositiveInt, parse_obj_as

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


DEFAULT_DOCKER_MANIFEST_CMD_TIMEOUT_S: Final[int] = 30


async def get_image_size_on_remote(image_name: str) -> ByteSize:
    async with aiodocker.Docker() as docker:
        docker_platform_info = await docker.system.info()
    local_arch = docker_platform_info.get("Architecture", "amd64")
    local_os = docker_platform_info.get("OSType", "linux")
    if local_arch == "x86_64":
        local_arch = "amd64"
    logger.debug("getting image size on remote using %s", f"{local_arch=}, {local_os=}")
    command = ["docker", "manifest", "inspect", "--verbose", f"{image_name}"]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    await asyncio.wait_for(
        process.wait(), timeout=DEFAULT_DOCKER_MANIFEST_CMD_TIMEOUT_S
    )
    assert process.returncode is not None  # nosec
    logger.debug(
        "getting image size on remote using %s, completed process with %s",
        f"{local_arch=}, {local_os=}",
        f"{process.returncode=}",
    )
    if process.returncode > 0:
        raise RuntimeError(
            f"unexpected error running '{' '.join(command)}': {stderr.decode()}"
        )

    all_manifests = json.loads(stdout.decode())
    local_arch_manifest = next(
        iter(
            filter(
                lambda x: (
                    x.get("Descriptor", {}).get("platform", {}).get("architecture")
                    == local_arch
                )
                and (x.get("Descriptor", {}).get("platform", {}).get("os") == local_os),
                all_manifests,
            )
        )
    )
    logger.debug("found %s", f"{local_arch_manifest=}")
    image_layers = local_arch_manifest.get("SchemaV2Manifest", {}).get("layers", [])
    layer_to_sizes = {
        layer["digest"]: layer["size"]
        for layer in image_layers
        if all(x in layer for x in ["digest", "size"])
    }
    logger.debug("found %s", f"{layer_to_sizes=}")
    image_size = parse_obj_as(ByteSize, sum(layer_to_sizes.values()))
    return image_size
