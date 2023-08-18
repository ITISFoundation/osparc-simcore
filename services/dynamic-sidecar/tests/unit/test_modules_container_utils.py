# pylint: disable=redefined-outer-name

import contextlib
from collections.abc import AsyncIterable

import aiodocker
import pytest
from simcore_service_dynamic_sidecar.modules.container_utils import (
    ContainerExecContainerNotFoundError,
    ContainerExecTimeoutError,
    run_command_in_container,
)


@pytest.fixture
async def running_container_name() -> AsyncIterable[str]:
    async with aiodocker.Docker() as client:
        container = await client.containers.run(
            config={
                "Image": "alpine:latest",
                "Cmd": ["/bin/ash", "-c", "sleep 10000"],
            }
        )
        container_inspect = await container.show()

        yield container_inspect["Name"][1:]

        with contextlib.suppress(aiodocker.DockerError):
            await container.kill()
        await container.delete()


async def test_run_command_in_container_container_not_found():
    with pytest.raises(ContainerExecContainerNotFoundError):
        await run_command_in_container("missing_container", command="")


async def test_run_command_in_container_command_timed_out(running_container_name: str):
    with pytest.raises(ContainerExecTimeoutError):
        await run_command_in_container(
            running_container_name, command="sleep 10", timeout=0.1
        )


async def test_(running_container_name: str):
    result = await run_command_in_container(running_container_name, command="ls -lah")
    assert len(result) > 0
