import asyncio
import logging
import uuid
from pprint import pformat
from typing import Awaitable, Optional

import aiodocker
from aiodocker.containers import DockerContainer

logger = logging.getLogger(__name__)


def wrap_async_call(fct: Awaitable) -> ...:
    return asyncio.get_event_loop().run_until_complete(fct)


def cluster_id() -> Optional[str]:
    """Returns the cluster id this docker engine belongs to, if any"""

    async def async_get_engine_cluster_id() -> Optional[str]:
        async with aiodocker.Docker() as docker:
            docker_system_info = await docker.system.info()
        node_labels = docker_system_info.get("Labels", [])

        for entry in node_labels:
            try:
                key, value = f"{entry}".split("=", maxsplit=1)
                if key == "cluster_id" and value:
                    return value
            except ValueError:
                logger.warning(
                    "The docker engine labels are not following the pattern `key=value`. Please check %s",
                    entry,
                )

    return wrap_async_call(async_get_engine_cluster_id())


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

                container_data = await container.wait(timeout=30)
                container_logs = await container.log(stdout=True, stderr=True)
                num_gpus = (
                    len(container_logs) if container_data["StatusCode"] == 0 else 0
                )
                logger.debug(
                    "testing for GPU presence with docker run %s %s completed with status code %s, found %d gpus:\nlogs:\n%s",
                    spec_config["Image"],
                    spec_config["Cmd"],
                    container_data["StatusCode"],
                    num_gpus,
                    pformat(container_logs),
                )
            except aiodocker.exceptions.DockerError as err:
                logger.debug(
                    "num_gpus DockerError while check-run %s: %s", spec_config, err
                )
            finally:
                if container is not None:
                    # ensure container is removed
                    await container.delete()

            return num_gpus

    return wrap_async_call(async_num_available_gpus())
