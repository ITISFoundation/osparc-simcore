# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from typing import cast
from uuid import UUID

import pytest
import redis.asyncio as aioredis
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.async_utils import cancel_wait_task
from servicelib.project_lock import (
    get_project_locked_state,
    is_project_locked,
    with_project_locked,
)
from servicelib.redis._client import RedisClientSDK
from simcore_service_webserver.projects.exceptions import ProjectLockError
from simcore_service_webserver.projects.lock import PROJECT_REDIS_LOCK_KEY
from simcore_service_webserver.redis import get_redis_lock_manager_client_sdk
from simcore_service_webserver.users.api import FullNameDict


@pytest.fixture()
def project_uuid(faker: Faker) -> ProjectID:
    return cast(UUID, faker.uuid4(cast_to=None))


@pytest.fixture()
def redis_client_from_app(client: TestClient) -> RedisClientSDK:
    assert client.app
    return get_redis_lock_manager_client_sdk(client.app)


async def test_with_locked_project_from_app(
    redis_client_from_app: RedisClientSDK,
    user_id: UserID,
    project_uuid: ProjectID,
    redis_locks_client: aioredis.Redis,
    faker: Faker,
):
    user_fullname: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }

    @with_project_locked(
        redis_client_from_app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        owner=Owner(user_id=user_id, **user_fullname),
    )
    async def _project_locked_fct() -> None:
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

    await _project_locked_fct()

    # once the lock is released, the value goes away
    redis_value = await redis_locks_client.get(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid)
    )
    assert not redis_value


async def test_lock_already_locked_project_raises(
    redis_client_from_app: RedisClientSDK,
    user_id: UserID,
    project_uuid: ProjectID,
    faker: Faker,
):
    user_fullname: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }

    started_event = asyncio.Event()

    @with_project_locked(
        redis_client_from_app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        owner=Owner(user_id=user_id, **user_fullname),
    )
    async def _locked_fct() -> None:
        started_event.set()
        await asyncio.sleep(10)

    task1 = asyncio.create_task(_locked_fct(), name="pytest_task_1")
    await started_event.wait()
    with pytest.raises(ProjectLockError):
        await _locked_fct()

    await cancel_wait_task(task1)


async def test_raise_exception_while_locked_release_lock(
    redis_client_from_app: RedisClientSDK,
    user_id: UserID,
    project_uuid: ProjectID,
    redis_locks_client: aioredis.Redis,
    faker: Faker,
):
    user_fullname: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }

    @with_project_locked(
        redis_client_from_app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        owner=Owner(user_id=user_id, **user_fullname),
    )
    async def _locked_fct() -> None:
        # here we have the project locked
        redis_value = await redis_locks_client.get(
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
        assert redis_value
        # now raising an exception
        msg = "pytest exception"
        raise ValueError(msg)

    with pytest.raises(ValueError, match="pytest exception"):
        await _locked_fct()
    # now the lock shall be released
    redis_value = await redis_locks_client.get(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid)
    )
    assert not redis_value


async def test_is_project_locked(
    redis_client_from_app: RedisClientSDK,
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    faker: Faker,
):
    assert client.app
    assert await is_project_locked(redis_client_from_app, project_uuid) is False
    user_fullname: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }

    @with_project_locked(
        redis_client_from_app,
        project_uuid=project_uuid,
        status=ProjectStatus.EXPORTING,
        owner=Owner(user_id=user_id, **user_fullname),
    )
    async def _locked_fct() -> None:
        assert client.app
        assert await is_project_locked(redis_client_from_app, project_uuid) is True

    await _locked_fct()
    assert await is_project_locked(redis_client_from_app, project_uuid) is False


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
    redis_client_from_app: RedisClientSDK,
    client: TestClient,
    user_id: UserID,
    project_uuid: ProjectID,
    faker: Faker,
    lock_status: ProjectStatus,
):
    assert client.app
    # no lock
    assert await get_project_locked_state(redis_client_from_app, project_uuid) is None

    assert await is_project_locked(redis_client_from_app, project_uuid) is False
    user_fullname: FullNameDict = {
        "first_name": faker.first_name(),
        "last_name": faker.last_name(),
    }

    @with_project_locked(
        redis_client_from_app,
        project_uuid=project_uuid,
        status=lock_status,
        owner=Owner(user_id=user_id, **user_fullname),
    )
    async def _locked_fct() -> None:
        assert client.app
        locked_state = await get_project_locked_state(
            redis_client_from_app, project_uuid
        )
        expected_locked_state = ProjectLocked(
            value=bool(lock_status not in [ProjectStatus.CLOSED, ProjectStatus.OPENED]),
            owner=Owner(user_id=user_id, **user_fullname),
            status=lock_status,
        )
        assert locked_state == expected_locked_state

    await _locked_fct()
