from asyncio import AbstractEventLoop
from typing import Type

# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
import aiodocker
import pytest
import tenacity


class _NotInSwarmException(Exception):
    pass


class _StillInSwarmException(Exception):
    pass


async def _in_docker_swarm(
    docker_client: aiodocker.docker.Docker, raise_error: bool = False
) -> bool:
    try:
        inspect_result = await docker_client.swarm.inspect()
        assert type(inspect_result) == dict
    except aiodocker.exceptions.DockerError as error:
        assert error.status == 503
        assert error.message.startswith("This node is not a swarm manager")
        if raise_error:
            raise _NotInSwarmException() from error
        return False
    return True


def _attempt_for(retry_error_cls: Type[Exception]) -> tenacity.AsyncRetrying:
    return tenacity.AsyncRetrying(
        wait=tenacity.wait_exponential(),
        stop=tenacity.stop_after_delay(15),
        retry_error_cls=retry_error_cls,
    )


@pytest.fixture(scope="module")
async def _docker_client(loop: AbstractEventLoop) -> aiodocker.docker.Docker:
    # name avoids collision with already used name
    async with aiodocker.Docker() as docker:
        yield docker


@pytest.fixture(scope="module")
async def async_docker_swarm(_docker_client: aiodocker.docker.Docker) -> None:
    async for attempt in _attempt_for(retry_error_cls=_NotInSwarmException):
        with attempt:
            if not await _in_docker_swarm(_docker_client):
                await _docker_client.swarm.init()
            # if still not in swarm raises an error to try and initialize again
            await _in_docker_swarm(_docker_client, raise_error=True)

    assert await _in_docker_swarm(_docker_client) is True

    yield

    async for attempt in _attempt_for(retry_error_cls=_StillInSwarmException):
        with attempt:
            if await _in_docker_swarm(_docker_client):
                await _docker_client.swarm.leave(force=True)
            # if still in swarm raises an error to try and leave again
            if await _in_docker_swarm(_docker_client):
                raise _StillInSwarmException()

    assert await _in_docker_swarm(_docker_client) is False
