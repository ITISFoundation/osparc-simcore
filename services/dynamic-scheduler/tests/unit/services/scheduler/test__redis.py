# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from pydantic import TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.generic_scheduler import ScheduleId
from simcore_service_dynamic_scheduler.services.scheduler._models import (
    UserRequestedState,
)
from simcore_service_dynamic_scheduler.services.scheduler._redis import (
    RedisServiceStateManager,
)

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture
def app_environment(
    disable_deferred_manager_lifespan: None,
    disable_rabbitmq_lifespan: None,
    disable_generic_scheduler_lifespan: None,
    disable_postgres_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def schedule_id(faker: Faker) -> ScheduleId:
    return faker.uuid4()


@pytest.fixture
def dynamic_service_start() -> DynamicServiceStart:
    return TypeAdapter(DynamicServiceStart).validate_python(
        DynamicServiceStart.model_json_schema()["example"]
    )


@pytest.fixture
def dynamic_service_stop() -> DynamicServiceStop:
    return TypeAdapter(DynamicServiceStop).validate_python(
        DynamicServiceStop.model_json_schema()["example"]
    )


async def test_redis_service_state(
    app: FastAPI,
    node_id: NodeID,
    schedule_id: ScheduleId,
    dynamic_service_start: DynamicServiceStart,
    dynamic_service_stop: DynamicServiceStop,
):
    state_manager = RedisServiceStateManager(app=app, node_id=node_id)

    # 1. check nothing present
    assert await state_manager.exists() is False
    assert await state_manager.read("desired_state") is None
    assert await state_manager.read("desired_start_data") is None
    assert await state_manager.read("desired_stop_data") is None
    assert await state_manager.read("current_start_data") is None
    assert await state_manager.read("current_stop_data") is None
    assert await state_manager.read("current_schedule_id") is None
    # reading does not create items
    assert await state_manager.exists() is False

    # 2. create some entries
    await state_manager.create_or_update("desired_state", UserRequestedState.RUNNING)
    # already works with one entry regarless of which one is
    assert await state_manager.exists() is True
    assert await state_manager.read("desired_state") == UserRequestedState.RUNNING

    await state_manager.create_or_update("current_state", UserRequestedState.STOPPED)
    assert await state_manager.read("current_state") == UserRequestedState.STOPPED

    await state_manager.create_or_update("current_schedule_id", schedule_id)
    assert await state_manager.read("current_schedule_id") == schedule_id

    await state_manager.create_or_update("current_start_data", dynamic_service_start)
    assert await state_manager.read("current_start_data") == dynamic_service_start
    await state_manager.create_or_update("desired_start_data", dynamic_service_start)
    assert await state_manager.read("desired_start_data") == dynamic_service_start

    await state_manager.create_or_update("current_stop_data", dynamic_service_stop)
    assert await state_manager.read("current_stop_data") == dynamic_service_stop
    await state_manager.create_or_update("desired_stop_data", dynamic_service_stop)
    assert await state_manager.read("desired_stop_data") == dynamic_service_stop
    # still true regardless of how many entries
    assert await state_manager.exists() is True

    # 3. remove nothig is presnet any longer
    await state_manager.delete()
    assert await state_manager.exists() is False

    # 4 setting multiple is the same

    await state_manager.create_or_update_multiple(
        {
            "desired_state": UserRequestedState.STOPPED,
            "desired_stop_data": dynamic_service_stop,
            "desired_start_data": dynamic_service_start,
            "current_schedule_id": schedule_id,
            "current_state": UserRequestedState.STOPPED,
            "current_start_data": dynamic_service_start,
            "current_stop_data": dynamic_service_stop,
        }
    )
    assert await state_manager.exists() is True
    assert await state_manager.read("desired_state") == UserRequestedState.STOPPED
    assert await state_manager.read("desired_start_data") == dynamic_service_start
    assert await state_manager.read("desired_stop_data") == dynamic_service_stop
    assert await state_manager.read("current_schedule_id") == schedule_id
    assert await state_manager.read("current_state") == UserRequestedState.STOPPED
    assert await state_manager.read("current_start_data") == dynamic_service_start
    assert await state_manager.read("current_stop_data") == dynamic_service_stop

    # 5. remove nothig is presnet any longer
    await state_manager.delete()
    assert await state_manager.exists() is False

    # 6. deleting a key
    await state_manager.create_or_update("current_schedule_id", schedule_id)
    assert await state_manager.read("current_schedule_id") == schedule_id
    await state_manager.delete_key("current_schedule_id")
    assert await state_manager.read("current_schedule_id") is None
    # can also delete unexising key withtout errors
    await state_manager.delete_key("current_schedule_id")
