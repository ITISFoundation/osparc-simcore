# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from typing import cast
from uuid import UUID

import pytest
from faker import Faker
from models_library.projects import ProjectID
from servicelib.redis import RedisClientSDK
from servicelib.redis._project_document_version import (
    increment_and_return_project_document_version,
)

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture()
def project_uuid(faker: Faker) -> ProjectID:
    return cast(UUID, faker.uuid4(cast_to=None))


async def test_project_document_version_workflow(
    redis_client_sdk: RedisClientSDK, project_uuid: ProjectID
):
    """Test the complete workflow of getting and incrementing project document versions."""

    # First increment should return 1
    new_version = await increment_and_return_project_document_version(
        redis_client_sdk, project_uuid
    )
    assert new_version == 1

    # Second increment should return 2
    new_version = await increment_and_return_project_document_version(
        redis_client_sdk, project_uuid
    )
    assert new_version == 2

    # Multiple increments should work correctly
    for expected_version in range(3, 6):
        new_version = await increment_and_return_project_document_version(
            redis_client_sdk, project_uuid
        )
        assert new_version == expected_version
