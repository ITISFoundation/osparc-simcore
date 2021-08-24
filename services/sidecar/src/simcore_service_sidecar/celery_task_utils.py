import logging
import subprocess
import uuid
from pprint import pformat

import aiodocker

from . import config
from .mpi_lock import acquire_mpi_lock
from .utils import wrap_async_call

log = logging.getLogger(__name__)


def on_task_failure_handler(
    self, exc, task_id, args, kwargs, einfo
):  # pylint: disable=unused-argument, too-many-arguments
    log.error(
        "Error while executing task %s with args=%s, kwargs=%s: %s",
        task_id,
        args if args else "none",
        pformat(kwargs) if kwargs else "none",
        exc,
    )


def on_task_retry_handler(
    self, exc, task_id, args, kwargs, einfo
):  # pylint: disable=unused-argument, too-many-arguments
    log.warning(
        "Retrying task %s with args=%s, kwargs=%s: %s",
        task_id,
        args if args else "none",
        pformat(kwargs) if kwargs else "none",
        exc,
    )


def on_task_success_handler(
    self, retval, task_id, args, kwargs
):  # pylint: disable=unused-argument
    log.info(
        "Task %s completed successfully with args=%s, kwargs=%s",
        task_id,
        args if args else "none",
        pformat(kwargs) if kwargs else "none",
    )


def start_as_mpi_node() -> bool:
    """
    Checks if this node can be a taraget to start as an MPI node.
    If it can it will try to grab a Redlock, ensure it is the only service who can be
    started as MPI.
    """

    with subprocess.Popen(  # nosec
        "cat /proc/cpuinfo | grep processor | wc -l",
        shell=True,
        stdout=subprocess.PIPE,
    ) as proc:
        assert proc.stdout  # nosec
        command_output = proc.stdout.read()

    current_cpu_count: int = int(command_output)
    if current_cpu_count != config.TARGET_MPI_NODE_CPU_COUNT:
        return False

    # it the mpi_lock is acquired, this service must start as MPI node
    is_mpi_node = acquire_mpi_lock(current_cpu_count)
    return is_mpi_node


def is_gpu_node() -> bool:
    """Returns True if this node has support to GPU,
    meaning that the `VRAM` label was added to it."""

    async def async_is_gpu_node() -> bool:
        async with aiodocker.Docker() as docker:
            spec_config = {
                "Cmd": "nvidia-smi",
                "Image": "nvidia/cuda:10.0-base",
                "AttachStdin": False,
                "AttachStdout": False,
                "AttachStderr": False,
                "Tty": False,
                "OpenStdin": False,
                "HostConfig": {
                    "Init": True,
                    "AutoRemove": True,
                },  # NOTE: The Init parameter shows a weird behavior: no exception thrown when the container fails
            }
            try:
                container = await docker.containers.run(
                    config=spec_config, name=f"sidecar_{uuid.uuid4()}_test_gpu"
                )

                container_data = await container.wait(timeout=30)
                log.debug(
                    "testing for GPU presence with docker run %s %s completed with status code %s:",
                    spec_config["Image"],
                    spec_config["Cmd"],
                    container_data["StatusCode"],
                )
                return container_data["StatusCode"] == 0
            except aiodocker.exceptions.DockerError as err:
                log.debug(
                    "is_gpu_node DockerError while check-run %s: %s", spec_config, err
                )

            return False

    has_gpu = wrap_async_call(async_is_gpu_node())
    return has_gpu
