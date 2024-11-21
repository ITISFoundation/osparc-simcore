import asyncio
import logging
import uuid
from collections.abc import Awaitable, Coroutine
from typing import Any, cast

import aiodocker
from aiodocker.containers import DockerContainer
from pydantic import ByteSize, TypeAdapter

logger = logging.getLogger(__name__)


def _wrap_async_call(fct: Awaitable[Any]) -> Any:
    return asyncio.get_event_loop().run_until_complete(fct)


def _nvidia_smi_docker_config(cmd: list[str]) -> dict[str, Any]:
    return {
        "Cmd": ["nvidia-smi", *cmd],
        "Image": "nvidia/cuda:12.2.0-base-ubuntu22.04",
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": False,
        "OpenStdin": False,
        "HostConfig": {
            "Init": True,
            "AutoRemove": False,  # NOTE: this cannot be True as we need the logs of the container before removing it
            "LogConfig": {"Type": "json-file"},
        },  # NOTE: The Init parameter shows a weird behavior: no exception thrown when the container fails
    }


def num_available_gpus() -> int:
    """Returns the number of available GPUs, 0 if not a gpu node"""

    async def async_num_available_gpus() -> int:
        num_gpus = 0
        container: DockerContainer | None = None
        async with aiodocker.Docker() as docker:
            spec_config = _nvidia_smi_docker_config(["--list-gpus"])
            try:
                container = await docker.containers.run(
                    config=spec_config, name=f"sidecar_{uuid.uuid4()}_test_gpu"
                )
                if not container:
                    return 0

                container_data = await container.wait(timeout=10)
                container_logs = await cast(
                    Coroutine,
                    container.log(stdout=True, stderr=True, follow=False),
                )
                num_gpus = (
                    len(container_logs)
                    if container_data.setdefault("StatusCode", 127) == 0
                    else 0
                )
            except TimeoutError as err:
                logger.warning(
                    "num_gpus timedout while check-run %s: %s", spec_config, err
                )
            except aiodocker.exceptions.DockerError as err:
                logger.warning(
                    "num_gpus DockerError while check-run %s: %s", spec_config, err
                )
            finally:
                if container is not None:
                    await container.delete(v=True, force=True)

            return num_gpus

    return cast(int, _wrap_async_call(async_num_available_gpus()))


def video_memory() -> int:
    """Returns the amount of VRAM available in bytes. 0 if no GPU available"""

    async def async_video_memory() -> int:
        video_ram: ByteSize = ByteSize(0)
        container: DockerContainer | None = None
        async with aiodocker.Docker() as docker:
            spec_config = _nvidia_smi_docker_config(
                [
                    "--query-gpu=memory.total",
                    "--format=csv,noheader",
                ]
            )

            try:
                container = await docker.containers.run(
                    config=spec_config, name=f"sidecar_{uuid.uuid4()}_test_gpu_memory"
                )
                if not container:
                    return 0

                container_data = await container.wait(timeout=10)
                container_logs = await cast(
                    Coroutine,
                    container.log(stdout=True, stderr=True, follow=False),
                )
                video_ram = TypeAdapter(ByteSize).validate_python(0)
                if container_data.setdefault("StatusCode", 127) == 0:
                    for line in container_logs:
                        video_ram = TypeAdapter(ByteSize).validate_python(
                            video_ram + TypeAdapter(ByteSize).validate_python(line)
                        )

            except TimeoutError as err:
                logger.warning(
                    "num_gpus timedout while check-run %s: %s", spec_config, err
                )
            except aiodocker.exceptions.DockerError as err:
                logger.warning(
                    "num_gpus DockerError while check-run %s: %s", spec_config, err
                )
            finally:
                if container is not None:
                    await container.delete(v=True, force=True)

            return video_ram

    return cast(int, _wrap_async_call(async_video_memory()))
