# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from typing import cast
from uuid import UUID

import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_access import Owner
from models_library.projects_state import ProjectLocked, ProjectStatus
from servicelib.async_utils import cancel_wait_task
from servicelib.redis import (
    PROJECT_REDIS_LOCK_KEY,
    ProjectLockError,
    RedisClientSDK,
    get_project_locked_state,
    is_project_locked,
    with_project_locked,
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


assert "json_schema_extra" in Owner.model_config
assert isinstance(Owner.model_config["json_schema_extra"], dict)
assert isinstance(Owner.model_config["json_schema_extra"]["examples"], list)


@pytest.fixture(params=Owner.model_config["json_schema_extra"]["examples"])
def owner(request: pytest.FixtureRequest) -> Owner:
    return Owner(**request.param)


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
):
    @with_project_locked(
        redis_client_sdk,
        project_uuid=project_uuid,
        status=project_status,
        owner=owner,
    )
    async def _locked_fct() -> None:
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
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
        assert redis_lock
        assert ProjectLocked.model_validate_json(redis_lock) == ProjectLocked(
            value=True,
            owner=owner,
            status=project_status,
        )

    assert await get_project_locked_state(redis_client_sdk, project_uuid) is None
    assert await is_project_locked(redis_client_sdk, project_uuid) is False
    await _locked_fct()
    assert await is_project_locked(redis_client_sdk, project_uuid) is False
    assert await get_project_locked_state(redis_client_sdk, project_uuid) is None


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
    )
    async def _locked_fct() -> None:
        started_event.set()
        await asyncio.sleep(10)

    task1 = asyncio.create_task(_locked_fct(), name="pytest_task_1")
    await started_event.wait()
    with pytest.raises(ProjectLockError):
        await _locked_fct()

    await cancel_wait_task(task1)
