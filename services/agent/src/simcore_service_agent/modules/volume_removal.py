from aiodocker import Docker
from servicelib.utils import logged_gather
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random

from ..core.errors import CouldNotRemoveVolumesError
from .docker import delete_volume, docker_client


async def _remove_single_volume(
    docker: Docker, volume_name: str, attempts: int, sleep_s: float
) -> None:
    # we want to distribute concurrent requests in time to the docker engine API
    # waiting a random amount of time ensures concurrent tasks do not overload
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_random(max=sleep_s),
        reraise=True,
    ):
        with attempt:
            await delete_volume(docker, volume_name)


async def remove_volumes(
    volume_names: list[str],
    volume_removal_attempts: int,
    sleep_between_attempts_s: float,
) -> None:
    """
    Attempts to remove each individual volume a few times before giving up.
    Will rase an error if it does not manage to remove a volume.
    """
    async with docker_client() as docker:
        results = await logged_gather(
            *(
                _remove_single_volume(
                    docker,
                    volume_name,
                    volume_removal_attempts,
                    sleep_between_attempts_s,
                )
                for volume_name in volume_names
            ),
            reraise=False
        )
        errors = [r for r in results if r is not None]
        if errors:
            raise CouldNotRemoveVolumesError(errors=errors)
