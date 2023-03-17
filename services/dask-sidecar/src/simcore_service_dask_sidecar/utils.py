import asyncio
import logging
import uuid
from pprint import pformat
from typing import Any, Awaitable, Coroutine, Optional, cast

import aiodocker
from aiodocker.containers import DockerContainer
from pydantic import ByteSize, parse_obj_as

logger = logging.getLogger(__name__)


def _wrap_async_call(fct: Awaitable[Any]) -> Any:
    return asyncio.get_event_loop().run_until_complete(fct)


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
                container_logs = await cast(
                    Coroutine,
                    container.log(stdout=True, stderr=True, follow=False),
                )
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

    return cast(int, _wrap_async_call(async_num_available_gpus()))


def video_memory() -> int:
    """Returns the number of available GPUs, 0 if not a gpu node"""

    async def async_video_memory() -> int:
        video_ram: ByteSize = ByteSize(0)
        container: Optional[DockerContainer] = None
        async with aiodocker.Docker() as docker:
            spec_config = {
                "Cmd": [
                    "nvidia-smi",
                    "--query-gpu=memory.total",
                    "--format=csv,noheader",
                ],
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
                container_logs = await cast(
                    Coroutine,
                    container.log(stdout=True, stderr=True, follow=False),
                )
                video_ram = parse_obj_as(ByteSize, 0)
                if container_data.setdefault("StatusCode", 127) == 0:
                    for line in container_logs:
                        video_ram = parse_obj_as(
                            ByteSize, video_ram + parse_obj_as(ByteSize, line)
                        )

                logger.debug(
                    "testing for GPU VRAM with docker run %s %s completed with status code %s, found %d total vram:\nlogs:\n%s",
                    spec_config["Image"],
                    spec_config["Cmd"],
                    container_data["StatusCode"],
                    video_ram.human_readable(),
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

            return video_ram

    return cast(int, _wrap_async_call(async_video_memory()))
