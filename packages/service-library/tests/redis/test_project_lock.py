# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from typing import cast
from unittest import mock
from uuid import UUID

import pytest
from common_library.async_tools import cancel_wait_task
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from servicelib.redis import (
    ProjectLockError,
    RedisClientSDK,
    get_project_locked_state,
    has_project_read_locks,
    is_project_locked,
    with_project_locked,
    with_project_read_locked,
)
from servicelib.redis._project_lock import _PROJECT_REDIS_LOCK_KEY

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture()
def project_uuid(faker: Faker) -> ProjectID:
    return cast(UUID, faker.uuid4(cast_to=None))


assert "json_schema_extra" in Owner.model_config
assert isinstance(Owner.model_config["json_schema_extra"], dict)
assert isinstance(Owner.model_config["json_schema_extra"]["examples"], list)


@pytest.fixture(params=Owner.model_config["json_schema_extra"]["examples"])
def owner(request: pytest.FixtureRequest) -> Owner:
    return Owner(**request.param)


@pytest.fixture
def mocked_notification_cb() -> mock.AsyncMock:
    return mock.AsyncMock()


@pytest.mark.parametrize(
    "project_status",
    [
        ProjectStatus.CLOSING,
        ProjectStatus.CLONING,
        ProjectStatus.EXPORTING,
        ProjectStatus.OPENING,
        ProjectStatus.MAINTAINING,
    ],
)
async def test_with_project_locked(
    redis_client_sdk: RedisClientSDK,
    project_uuid: ProjectID,
    owner: Owner,
    project_status: ProjectStatus,
    mocked_notification_cb: mock.AsyncMock,
):
    @with_project_locked(
        redis_client_sdk,
        project_uuid=project_uuid,
        status=project_status,
        owner=owner,
        notification_cb=mocked_notification_cb,
    )
    async def _locked_fct() -> None:
        mocked_notification_cb.assert_called_once()
        assert await is_project_locked(redis_client_sdk, project_uuid) is True
        locked_state = await get_project_locked_state(redis_client_sdk, project_uuid)
        assert locked_state is not None
        assert locked_state == ProjectLocked(
            value=True,
            owner=owner,
            status=project_status,
        )
        # check lock name formatting is correct
        redis_lock = await redis_client_sdk.redis.get(_PROJECT_REDIS_LOCK_KEY.format(project_uuid))
        assert redis_lock
        assert ProjectLocked.model_validate_json(redis_lock) == ProjectLocked(
            value=True,
            owner=owner,
            status=project_status,
        )

    mocked_notification_cb.assert_not_called()
    assert await get_project_locked_state(redis_client_sdk, project_uuid) is None
    assert await is_project_locked(redis_client_sdk, project_uuid) is False
    await _locked_fct()
    assert await is_project_locked(redis_client_sdk, project_uuid) is False
    assert await get_project_locked_state(redis_client_sdk, project_uuid) is None
    mocked_notification_cb.assert_called()
    assert mocked_notification_cb.call_count == 2


@pytest.mark.parametrize(
    "project_status",
    [
        ProjectStatus.CLOSING,
        ProjectStatus.CLONING,
        ProjectStatus.EXPORTING,
        ProjectStatus.OPENING,
        ProjectStatus.MAINTAINING,
    ],
)
async def test_lock_already_locked_project_raises(
    redis_client_sdk: RedisClientSDK,
    project_uuid: ProjectID,
    owner: Owner,
    project_status: ProjectStatus,
):
    started_event = asyncio.Event()

    @with_project_locked(
        redis_client_sdk,
        project_uuid=project_uuid,
        status=project_status,
        owner=owner,
        notification_cb=None,
    )
    async def _locked_fct() -> None:
        started_event.set()
        await asyncio.sleep(10)

    task1 = asyncio.create_task(_locked_fct(), name="pytest_task_1")
    await started_event.wait()
    with pytest.raises(ProjectLockError):
        await _locked_fct()

    await cancel_wait_task(task1)


async def test_project_read_locks_allow_concurrent_readers(
    redis_client_sdk: RedisClientSDK,
    project_uuid: ProjectID,
    owner: Owner,
):
    both_readers_started = asyncio.Event()
    release_readers = asyncio.Event()
    active_readers = 0

    @with_project_read_locked(
        redis_client_sdk,
        project_uuid=project_uuid,
        status=ProjectStatus.CLONING,
        owner=owner,
    )
    async def _read_project() -> None:
        nonlocal active_readers
        active_readers += 1
        if active_readers == 2:
            both_readers_started.set()
        await release_readers.wait()

    reader_tasks = [asyncio.create_task(_read_project()) for _ in range(2)]
    await both_readers_started.wait()
    assert await has_project_read_locks(redis_client_sdk, project_uuid)

    release_readers.set()
    await asyncio.gather(*reader_tasks)

    assert await has_project_read_locks(redis_client_sdk, project_uuid) is False


async def test_project_read_lock_waits_for_writer_before_entering(
    redis_client_sdk: RedisClientSDK,
    project_uuid: ProjectID,
    owner: Owner,
):
    writer_started = asyncio.Event()
    release_writer = asyncio.Event()
    reader_started = asyncio.Event()
    writer_finished = False

    @with_project_locked(
        redis_client_sdk,
        project_uuid=project_uuid,
        status=ProjectStatus.CLOSING,
        owner=owner,
        notification_cb=None,
    )
    async def _write_project() -> None:
        nonlocal writer_finished
        writer_started.set()
        await release_writer.wait()
        writer_finished = True

    @with_project_read_locked(
        redis_client_sdk,
        project_uuid=project_uuid,
        status=ProjectStatus.CLONING,
        owner=owner,
    )
    async def _read_project() -> None:
        assert writer_finished
        reader_started.set()

    writer_task = asyncio.create_task(_write_project())
    await writer_started.wait()
    reader_task = asyncio.create_task(_read_project())
    await asyncio.sleep(0)
    assert reader_started.is_set() is False
    assert await has_project_read_locks(redis_client_sdk, project_uuid) is False

    release_writer.set()
    await asyncio.gather(reader_task, writer_task)
    assert reader_started.is_set()
