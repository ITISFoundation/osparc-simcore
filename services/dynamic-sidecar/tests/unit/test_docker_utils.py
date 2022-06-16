# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from typing import AsyncIterable
from uuid import UUID

import aiodocker
from faker import Faker
import pytest
from simcore_service_dynamic_sidecar.core.docker_utils import get_volume_by_label
from simcore_service_dynamic_sidecar.core.errors import VolumeNotFoundError

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="session")
def volume_name() -> str:
    return "test_source_name"


@pytest.fixture
def observation_id(faker: Faker) -> UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
async def volume_with_label(
    volume_name: str, observation_id: str
) -> AsyncIterable[None]:
    async with aiodocker.Docker() as docker_client:
        volume = await docker_client.volumes.create(
            {
                "Name": "test_volume_name_1",
                "Labels": {
                    "source": volume_name,
                    "observation_id": f"{observation_id}",
                },
            }
        )

        yield

        await volume.delete()


async def test_volume_with_label(
    volume_with_label: None, volume_name: str, observation_id: UUID
) -> None:
    assert await get_volume_by_label(volume_name, observation_id)


async def test_volume_label_missing(observation_id: UUID) -> None:
    with pytest.raises(VolumeNotFoundError) as info:
        await get_volume_by_label("not_exist", observation_id)
    assert (
        info.value.args[0]
        == f"Expected 1 volume with source_label='not_exist', observation_id={observation_id}, query returned: []"
    )
