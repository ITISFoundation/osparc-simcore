# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument

from collections.abc import AsyncIterable, Callable
from unittest.mock import AsyncMock, call

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.services.generic_scheduler import (
    BaseStep,
    Operation,
    OperationName,
    ProvidedOperationContext,
    RequiredOperationContext,
    SingleStepGroup,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    OperationNotFoundError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._event_after import (
    AfterEventManager,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    EventType,
    OperationContext,
    OperationToStart,
    ScheduleId,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._store import (
    OperationEventsProxy,
    Store,
)
from utils import ensure_keys_in_store

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture
def app_environment(
    disable_postgres_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def app(app_environment: EnvVarsDict) -> AsyncIterable[FastAPI]:
    app = create_app()
    async with LifespanManager(app):
        yield app


@pytest.fixture
def after_event_manager(app: FastAPI) -> AfterEventManager:
    return AfterEventManager.get_from_app_state(app)


@pytest.fixture
def store(app: FastAPI) -> Store:
    return Store.get_from_app_state(app)


@pytest.fixture
def schedule_id(faker: Faker) -> ScheduleId:
    return TypeAdapter(ScheduleId).validate_python(faker.uuid4())


@pytest.fixture
def mock_start_operation(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_scheduler.services.generic_scheduler._event_after.start_operation",
        autospec=True,
    )


@pytest.mark.parametrize("event_type", EventType)
async def test_operation_is_missing(
    after_event_manager: AfterEventManager,
    schedule_id: ScheduleId,
    event_type: EventType,
):
    await ensure_keys_in_store(after_event_manager.app, expected_keys=set())

    with pytest.raises(OperationNotFoundError):
        await after_event_manager.register_to_start_after(
            schedule_id,
            event_type,
            to_start=OperationToStart(operation_name="missing_operation", initial_context={}),
        )
    await ensure_keys_in_store(after_event_manager.app, expected_keys=set())


class _BS(BaseStep):
    @classmethod
    async def execute(cls, app: FastAPI, required_context: RequiredOperationContext) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context


@pytest.mark.parametrize(
    "operation",
    [
        Operation(
            SingleStepGroup(_BS),
        ),
    ],
)
@pytest.mark.parametrize("event_type", EventType)
@pytest.mark.parametrize(
    "initial_context",
    [
        {"key": "value", "dict": {"some": "thing"}, "list": [1, 2, 3]},
    ],
)
async def test_workflow(
    after_event_manager: AfterEventManager,
    store: Store,
    schedule_id: ScheduleId,
    event_type: EventType,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    mock_start_operation: AsyncMock,
    initial_context: OperationContext,
):
    operation_name = "op1"

    register_operation(operation_name, operation)
    await ensure_keys_in_store(after_event_manager.app, expected_keys=set())

    await after_event_manager.register_to_start_after(
        schedule_id,
        event_type,
        to_start=OperationToStart(
            operation_name=operation_name,
            initial_context=initial_context,
        ),
    )
    await ensure_keys_in_store(
        after_event_manager.app,
        expected_keys={f"SCH:{schedule_id}:EVENTS:{event_type}"},
    )

    # ensure is still scheduled even when the DB entry is gone
    events_proxy = OperationEventsProxy(store, schedule_id, event_type)
    await events_proxy.delete()
    await ensure_keys_in_store(after_event_manager.app, expected_keys=set())

    await after_event_manager.safe_on_event_type(event_type, schedule_id, operation_name, initial_context)

    assert mock_start_operation.call_args_list == [call(after_event_manager.app, operation_name, initial_context)]
