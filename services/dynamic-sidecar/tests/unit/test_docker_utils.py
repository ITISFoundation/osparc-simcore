# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from typing import AsyncIterable

import aiodocker
import pytest
from simcore_service_dynamic_sidecar.core.docker_utils import get_volume_by_label
from simcore_service_dynamic_sidecar.core.errors import VolumeNotFoundError

pytestmark = pytest.mark.asyncio


@pytest.fixture
def volume_name() -> str:
    return "test_source_name"


@pytest.fixture
async def volume_with_label(volume_name: str) -> AsyncIterable[None]:
    async with aiodocker.Docker() as docker_client:
        volume = await docker_client.volumes.create(
            {"Name": "test_volume_name_1", "Labels": {"source": volume_name}}
        )

        yield

        await volume.delete()


async def test_volume_with_label(volume_with_label: None, volume_name: str) -> None:
    assert await get_volume_by_label(volume_name)


async def test_volume_label_missing() -> None:
    with pytest.raises(VolumeNotFoundError) as info:
        await get_volume_by_label("not_exist")
    assert info.value.args[0] == "Could not find desired volume, query returned []"
