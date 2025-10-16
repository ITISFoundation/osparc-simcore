# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import asyncio
from collections.abc import AsyncIterable
from enum import Enum
from typing import ClassVar
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from pydantic import NonNegativeInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.generic_scheduler._deferred_runner import (
    DeferredRunner,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    NoDataFoundError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    OperationName,
    ProvidedOperationContext,
    RequiredOperationContext,
    ScheduleId,
    StepStatus,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._operation import (
    BaseStep,
    BaseStepGroup,
    Operation,
    OperationRegistry,
    SingleStepGroup,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._store import (
    ScheduleDataStoreProxy,
    StepStoreProxy,
    Store,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

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
def store(app: FastAPI) -> Store:
    return Store.get_from_app_state(app)


@pytest.fixture
def schedule_id() -> ScheduleId:
    return "a-schedule-id"


@pytest.fixture
async def operation_name() -> OperationName:
    return "an-operation"


@pytest.fixture
async def registed_operation(
    operation_name: OperationName, operation: Operation
) -> AsyncIterable[None]:
    OperationRegistry.register(operation_name, operation)
    yield
    OperationRegistry.unregister(operation_name)


@pytest.fixture
def mock_enqueue_event(mocker: MockerFixture) -> AsyncMock:
    mock = AsyncMock()
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.generic_scheduler._deferred_runner.enqueue_schedule_event",
        mock,
    )
    return mock


async def _assert_finshed_with_status(
    step_proxy: StepStoreProxy, expected_status: StepStatus
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        reraise=True,
        retry=retry_if_exception_type((AssertionError, NoDataFoundError)),
    ):
        with attempt:
            assert await step_proxy.read("status") == expected_status


class _StepResultStore:
    _STORE: ClassVar[dict[str, str]] = {}

    @classmethod
    def set_result(cls, key: str, value: str) -> None:
        cls._STORE[key] = value

    @classmethod
    def get_result(cls, key: str) -> str:
        return cls._STORE[key]

    @classmethod
    def clear(cls) -> None:
        cls._STORE.clear()


class _StepFinisheWithSuccess(BaseStep):
    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _StepResultStore.set_result(cls.__name__, "executed")
        return {}

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _StepResultStore.set_result(cls.__name__, "destroyed")
        return {}


class _StepFinisheError(BaseStep):
    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _StepResultStore.set_result(cls.__name__, "executed")
        msg = "I failed creating"
        raise RuntimeError(msg)

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _StepResultStore.set_result(cls.__name__, "destroyed")
        msg = "I failed destorying"
        raise RuntimeError(msg)


class _StepLongRunningToCancel(BaseStep):
    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _StepResultStore.set_result(cls.__name__, "executed")
        await asyncio.sleep(1e6)
        return {}

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _StepResultStore.set_result(cls.__name__, "destroyed")
        await asyncio.sleep(1e6)
        return {}


class _Action(str, Enum):
    DO_NOTHING = "NOTHING"
    CANCEL = "CANCEL"


def _get_step_group(
    operation_name: OperationName, group_index: NonNegativeInt
) -> BaseStepGroup:
    assert operation_name in OperationRegistry._OPERATIONS  # noqa: SLF001

    operation = OperationRegistry._OPERATIONS[operation_name][  # noqa: SLF001
        "operation"
    ]
    operations_count = len(operation.step_groups)
    assert group_index < operations_count

    return operation.step_groups[group_index]


@pytest.mark.parametrize(
    "operation, expected_step_status, action, expected_steps_count",
    [
        (
            Operation(
                SingleStepGroup(_StepFinisheWithSuccess),
            ),
            StepStatus.SUCCESS,
            _Action.DO_NOTHING,
            1,
        ),
        (
            Operation(
                SingleStepGroup(_StepFinisheError),
            ),
            StepStatus.FAILED,
            _Action.DO_NOTHING,
            1,
        ),
        (
            Operation(
                SingleStepGroup(_StepLongRunningToCancel),
            ),
            StepStatus.RUNNING,
            _Action.CANCEL,
            1,
        ),
    ],
)
@pytest.mark.parametrize("is_executing", [True, False])
async def test_workflow(
    mock_enqueue_event: AsyncMock,
    registed_operation: None,
    app: FastAPI,
    store: Store,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    expected_step_status: StepStatus,
    is_executing: bool,
    action: _Action,
    expected_steps_count: NonNegativeInt,
) -> None:

    # setup
    schedule_data_proxy = ScheduleDataStoreProxy(store=store, schedule_id=schedule_id)
    await schedule_data_proxy.create_or_update_multiple(
        {
            "operation_name": operation_name,
            "group_index": 0,
            "is_executing": is_executing,
        }
    )

    step_group = _get_step_group(operation_name, 0)

    step_group_name = step_group.get_step_group_name(index=0)

    steps = step_group.get_step_subgroup_to_run()
    assert len(steps) == 1
    step = steps[0]

    step_name = step.get_step_name()

    step_proxy = StepStoreProxy(
        store=store,
        schedule_id=schedule_id,
        operation_name=operation_name,
        step_group_name=step_group_name,
        step_name=step_name,
        is_executing=is_executing,
    )

    ### tests starts here

    await DeferredRunner.start(
        schedule_id=schedule_id,
        operation_name=operation_name,
        step_group_name=step_group_name,
        step_name=step_name,
        is_executing=is_executing,
        expected_steps_count=expected_steps_count,
    )

    if action == _Action.CANCEL:
        await asyncio.sleep(0.2)  # give it some time to start

        task_uid = await step_proxy.read("deferred_task_uid")
        await asyncio.create_task(DeferredRunner.cancel(task_uid))

    await _assert_finshed_with_status(step_proxy, expected_step_status)

    assert _StepResultStore.get_result(step.__name__) == (
        "executed" if is_executing else "destroyed"
    )

    if expected_step_status == StepStatus.FAILED:
        error_traceback = await step_proxy.read("error_traceback")
        assert "I failed" in error_traceback

    # ensure called once with arguments

    assert (
        mock_enqueue_event.call_args_list == []
        if action == _Action.CANCEL
        else [((app, schedule_id),)]
    )
