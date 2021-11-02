import asyncio
import logging
import uuid
from pprint import pformat
from typing import Any, Awaitable, Optional, cast

import aiodocker
from aiodocker.containers import DockerContainer

from .settings import Settings

logger = logging.getLogger(__name__)


def wrap_async_call(fct: Awaitable[Any]) -> Any:
    return asyncio.get_event_loop().run_until_complete(fct)


def cluster_id() -> Optional[str]:
    """Returns the cluster id this docker engine belongs to, if any"""

    async def async_get_engine_cluster_id() -> Optional[str]:
        app_settings = Settings.create_from_envs()
        async with aiodocker.Docker() as docker:
            docker_system_info = await docker.system.info()
        node_labels = docker_system_info.get("Labels", [])

        for entry in node_labels:
            try:
                key, value = f"{entry}".split("=", maxsplit=1)
                if key == "cluster_id" and value:
                    return f"{app_settings.DASK_CLUSTER_ID_PREFIX}{value}"
            except ValueError:
                logger.warning(
                    "The docker engine labels are not following the pattern `key=value`. Please check %s",
                    entry,
                )
        return f"{app_settings.DASK_CLUSTER_ID_PREFIX}{app_settings.DASK_DEFAULT_CLUSTER_ID}"

    return cast(Optional[str], wrap_async_call(async_get_engine_cluster_id()))


def num_available_gpus() -> int:
    """Returns the number of available GPUs, 0 if not a gpu node"""

    async def async_num_available_gpus() -> int:
        num_gpus = 0
        container: Optional[DockerContainer] = None
        async with aiodocker.Docker() as docker:
            spec_config = {
                "Cmd": ["nvidia-smi", "--list-gpus"],
                "Image": "nvidia/cuda:10.0-base",
                "AttachStdin": False,
                "AttachStdout": False,
                "AttachStderr": False,
                "Tty": False,
                "OpenStdin": False,
                "HostConfig": {
                    "Init": True,
                    "AutoRemove": False,
                },  # NOTE: The Init parameter shows a weird behavior: no exception thrown when the container fails
            }
            try:
                container = await docker.containers.run(
                    config=spec_config, name=f"sidecar_{uuid.uuid4()}_test_gpu"
                )
                if not container:
                    return 0

                container_data = await container.wait(timeout=10)
                container_logs = await container.log(stdout=True, stderr=True)
                num_gpus = (
                    len(container_logs)
                    if container_data.setdefault("StatusCode", 127) == 0
                    else 0
                )
                logger.debug(
                    "testing for GPU presence with docker run %s %s completed with status code %s, found %d gpus:\nlogs:\n%s",
                    spec_config["Image"],
                    spec_config["Cmd"],
                    container_data["StatusCode"],
                    num_gpus,
                    pformat(container_logs),
                )
            except asyncio.TimeoutError as err:
                logger.warning(
                    "num_gpus timedout while check-run %s: %s", spec_config, err
                )
            except aiodocker.exceptions.DockerError as err:
                logger.warning(
                    "num_gpus DockerError while check-run %s: %s", spec_config, err
                )
            finally:
                if container is not None:
                    # ensure container is removed
                    await container.delete()

            return num_gpus

    return cast(int, wrap_async_call(async_num_available_gpus()))
