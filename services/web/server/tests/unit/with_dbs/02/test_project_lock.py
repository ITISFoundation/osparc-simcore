# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import redis.asyncio as aioredis
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_service_webserver.projects.exceptions import ProjectLockError
from simcore_service_webserver.projects.lock import (
    PROJECT_REDIS_LOCK_KEY,
    get_project_locked_state,
    is_project_locked,
    lock_project,
)
from simcore_service_webserver.users.api import FullNameDict


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
    user_fullname: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    async with lock_project(
        app=client.app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        user_id=user_id,
        user_fullname=user_fullname,
    ):
        redis_value = await redis_locks_client.get(
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
        assert redis_value
        lock_value = TypeAdapter(ProjectLocked).validate_json(redis_value)
        assert lock_value == ProjectLocked(
            value=True,
            owner=Owner(user_id=user_id, **user_fullname),
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
    user_name: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    async with lock_project(
        app=client.app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        user_id=user_id,
        user_fullname=user_name,
    ):
        # locking again is not permitted
        with pytest.raises(ProjectLockError):
            async with lock_project(
                app=client.app,
                project_uuid=project_uuid,
                status=ProjectStatus.OPENING,
                user_id=user_id,
                user_fullname=user_name,
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
    user_name: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    with pytest.raises(ValueError):
        async with lock_project(
            app=client.app,
            project_uuid=project_uuid,
            status=ProjectStatus.EXPORTING,
            user_id=user_id,
            user_fullname=user_name,
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


async def test_is_project_locked(
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    faker: Faker,
):
    assert client.app
    assert await is_project_locked(client.app, project_uuid) is False
    user_name: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    async with lock_project(
        app=client.app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        user_id=user_id,
        user_fullname=user_name,
    ):
        assert await is_project_locked(client.app, project_uuid) is True


@pytest.mark.parametrize(
    "lock_status",
    [
        ProjectStatus.CLOSING,
        ProjectStatus.CLONING,
        ProjectStatus.EXPORTING,
        ProjectStatus.OPENING,
    ],
)
async def test_get_project_locked_state(
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    faker: Faker,
    lock_status: ProjectStatus,
):
    assert client.app
    # no lock
    assert await get_project_locked_state(client.app, project_uuid) is None

    assert await is_project_locked(client.app, project_uuid) is False
    user_name: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }
    async with lock_project(
        app=client.app,
        project_uuid=project_uuid,
        status=lock_status,
        user_id=user_id,
        user_fullname=user_name,
    ):
        locked_state = await get_project_locked_state(client.app, project_uuid)
        expected_locked_state = ProjectLocked(
            value=bool(lock_status not in [ProjectStatus.CLOSED, ProjectStatus.OPENED]),
            owner=Owner(user_id=user_id, **user_name),
            status=lock_status,
        )
        assert locked_state == expected_locked_state
