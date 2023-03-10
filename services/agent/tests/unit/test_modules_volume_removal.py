import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

import pytest
from aiodocker import Docker, DockerError
from aiodocker.volumes import DockerVolume
from faker import Faker
from simcore_service_agent.core.errors import CouldNotRemoveVolumesError
from simcore_service_agent.modules.volume_removal import remove_volumes


@asynccontextmanager
async def create_volume(faker: Faker) -> AsyncIterator[DockerVolume]:
    async with Docker() as docker_client:
        volume = await docker_client.volumes.create(
            {"Name": f"test_vol{faker.uuid4()}"}
        )

        yield volume

        try:
            await volume.delete()
        except DockerError:
            pass


async def is_volume_present(volume_name: str) -> bool:
    async with Docker() as docker_client:
        try:
            await DockerVolume(docker_client, volume_name).show()
            return True
        except DockerError as e:
            return f"{volume_name}: no such volume" not in f"{e}"


async def test_remove_volumes(faker: Faker):
    async with AsyncExitStack() as exit_stack:
        volumes = await asyncio.gather(
            *(exit_stack.enter_async_context(create_volume(faker)) for _ in range(10))
        )

        for volume in volumes:
            assert await is_volume_present(volume.name) is True

        await remove_volumes(
            [v.name for v in volumes],
            volume_removal_attempts=15,
            sleep_between_attempts_s=3,
        )

        for volume in volumes:
            assert await is_volume_present(volume.name) is False


async def test_remove_volumes_a_volume_does_not_exist(faker: Faker):
    async with AsyncExitStack() as exit_stack:
        volumes = await asyncio.gather(
            *(exit_stack.enter_async_context(create_volume(faker)) for _ in range(10))
        )

        for volume in volumes:
            assert await is_volume_present(volume.name) is True

        volume_names = [v.name for v in volumes]
        volumes_to_remove = volume_names[:1] + ["fake_volume"] + volume_names[1:]
        assert len(volumes_to_remove) == len(volume_names) + 1

        with pytest.raises(
            CouldNotRemoveVolumesError, match="get fake_volume: no such volume"
        ):
            await remove_volumes(
                volumes_to_remove,
                volume_removal_attempts=3,
                sleep_between_attempts_s=0.1,
            )

        for volume in volumes:
            assert await is_volume_present(volume.name) is False
