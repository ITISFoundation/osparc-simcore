import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from aiodocker import Docker, DockerError
from aiodocker.execs import Exec
from aiodocker.stream import Stream
from pydantic import NonNegativeFloat
from starlette import status

from ..core.errors import (
    ContainerExecCommandFailedError,
    ContainerExecContainerNotFoundError,
    ContainerExecTimeoutError,
)

_logger = logging.getLogger(__name__)


async def _execute_command(container_name: str, command: str | Sequence[str]) -> str:
    async with Docker() as docker:
        container = await docker.containers.get(container_name)

        # Start the command inside the container
        exec_instance: Exec = await container.exec(
            cmd=command, stdout=True, stderr=True, tty=False
        )

        # Start the execution
        stream: Stream = exec_instance.start(detach=False)

        command_result: str = ""
        async with stream:
            while stream_message := await stream.read_out():
                command_result += stream_message.data.decode()

        inspect_result: dict[str, Any] = await exec_instance.inspect()
        exit_code: int | None = inspect_result.get("ExitCode", None)
        if exit_code != 0:
            raise ContainerExecCommandFailedError(
                command=command, exit_code=exit_code, command_result=command_result
            )

    _logger.debug("Command output:\n%s", command_result)
    return command_result


async def run_command_in_container(
    container_name: str,
    *,
    command: str | Sequence[str],
    timeout: NonNegativeFloat = 1.0,
):
    """
    Runs `command` in target container and returns the command's output if
    command's exit code is 0.

    Arguments:
        container_name -- name of the container in which to run the command
        command -- string or sequence of strings to run as command

    Keyword Arguments:
        timeout -- max time for the command to return a result in (default: {1.0})

    Raises:
        ContainerExecTimeoutError: command execution did not finish in time
        ContainerExecContainerNotFoundError: target container is not present
        ContainerExecCommandFailedError: command finished with not 0 exit code
        DockerError: propagates error from docker engine

    Returns:
        stdout + stderr produced by the command is returned
    """
    try:
        return await asyncio.wait_for(
            _execute_command(container_name, command), timeout
        )
    except DockerError as e:
        if e.status == status.HTTP_404_NOT_FOUND:
            raise ContainerExecContainerNotFoundError(
                container_name=container_name
            ) from e
        raise
    except asyncio.TimeoutError as e:
        raise ContainerExecTimeoutError(timeout=timeout, command=command) from e
