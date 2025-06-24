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
    is_project_locked,
    with_project_locked,
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
        redis_lock = await redis_client_sdk.redis.get(
            _PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
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
