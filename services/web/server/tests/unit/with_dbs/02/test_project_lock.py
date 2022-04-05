import aioredis
import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_state import ProjectStatus
from models_library.users import UserID
from simcore_service_webserver.projects.project_lock import (
    PROJECT_REDIS_LOCK_KEY,
    lock_project,
)


@pytest.fixture()
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture()
def project_uuid(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


async def test_lock_project(
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    redis_locks_client: aioredis.Redis,
):
    assert client.app
    async with lock_project(
        app=client.app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        user_id=user_id,
        user_name={"first_name": "pytest", "last_name": "smith"},
    ):
        redis_value = await redis_locks_client.get(
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
        assert redis_value
