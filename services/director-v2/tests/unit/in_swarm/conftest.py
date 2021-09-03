# pylint: disable=unused-argument
import aiodocker
import pytest
import tenacity


@pytest.fixture
async def docker_swarm(loop) -> None:
    # NOTE: overwrites existing fixture
    class _NotInSwarmException(Exception):
        pass

    class _StillInSwarmException(Exception):
        pass

    async def _in_docker_swarm(raise_error: bool = False) -> bool:

        try:
            async with aiodocker.Docker() as docker:
                inspect_result = await docker.swarm.inspect()
                assert type(inspect_result) == dict
        except aiodocker.exceptions.DockerError as error:
            assert error.status == 503
            assert error.message.startswith("This node is not a swarm manager")
            if raise_error:
                raise _NotInSwarmException() from error
            return False
        return True

    async with aiodocker.Docker() as docker:
        async for attempt in tenacity.AsyncRetrying(
            wait=tenacity.wait_exponential(),
            stop=tenacity.stop_after_delay(15),
            retry_error_cls=_NotInSwarmException,
        ):
            with attempt:
                if not await _in_docker_swarm():
                    await docker.swarm.init()
                # if still not in swarm raises an error to try and initialize again
                await _in_docker_swarm(raise_error=True)

        assert await _in_docker_swarm() is True

        yield

        async for attempt in tenacity.AsyncRetrying(
            wait=tenacity.wait_exponential(),
            stop=tenacity.stop_after_delay(15),
            retry_error_cls=_StillInSwarmException,
        ):
            with attempt:
                if await _in_docker_swarm():
                    await docker.swarm.leave(force=True)
                # if still in swarm raises an error to try and leave again
                if await _in_docker_swarm():
                    raise _StillInSwarmException()

        assert await _in_docker_swarm() is False
