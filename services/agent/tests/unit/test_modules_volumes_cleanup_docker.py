from aiodocker.volumes import DockerVolume
from simcore_service_agent.modules.volumes_cleanup._docker import (
    docker_client,
    is_volume_used,
)


async def test_is_volume_mounted_true(used_volume: DockerVolume):
    async with docker_client() as client:
        assert await is_volume_used(client, used_volume.name) is True


async def test_is_volume_mounted_false(unused_volume: DockerVolume):
    async with docker_client() as client:
        assert await is_volume_used(client, unused_volume.name) is False
