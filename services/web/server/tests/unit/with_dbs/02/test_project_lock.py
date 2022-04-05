# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import aioredis
import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from models_library.users import UserID
from pydantic import parse_raw_as
from simcore_service_webserver.projects.project_lock import (
    PROJECT_REDIS_LOCK_KEY,
    ProjectLockError,
    lock_project,
)
from simcore_service_webserver.users_api import UserNameDict


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
    faker: Faker,
):
    assert client.app
    user_name: UserNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    async with lock_project(
        app=client.app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        user_id=user_id,
        user_name=user_name,
    ):
        redis_value = await redis_locks_client.get(
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
        assert redis_value
        lock_value = parse_raw_as(ProjectLocked, redis_value)
        assert lock_value == ProjectLocked(
            value=True,
            owner=Owner(user_id=user_id, **user_name),
            status=ProjectStatus.EXPORTING,
        )

    # once the lock is released, the value goes away
    redis_value = await redis_locks_client.get(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid)
    )
    assert not redis_value


async def test_lock_already_locked_project_raises(
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    redis_locks_client: aioredis.Redis,
    faker: Faker,
):
    assert client.app
    user_name: UserNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    async with lock_project(
        app=client.app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        user_id=user_id,
        user_name=user_name,
    ):
        # locking again is not permitted
        with pytest.raises(ProjectLockError):
            async with lock_project(
                app=client.app,
                project_uuid=project_uuid,
                status=ProjectStatus.OPENING,
                user_id=user_id,
                user_name=user_name,
            ):
                ...


async def test_raise_exception_while_locked_release_lock(
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    redis_locks_client: aioredis.Redis,
    faker: Faker,
):
    assert client.app
    user_name: UserNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    with pytest.raises(ValueError):
        async with lock_project(
            app=client.app,
            project_uuid=project_uuid,
            status=ProjectStatus.EXPORTING,
            user_id=user_id,
            user_name=user_name,
        ):
            # here we have the project locked
            redis_value = await redis_locks_client.get(
                PROJECT_REDIS_LOCK_KEY.format(project_uuid)
            )
            assert redis_value
            # now raising an exception
            raise ValueError("pytest exception")
    # now the lock shall be released
    redis_value = await redis_locks_client.get(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid)
    )
    assert not redis_value
