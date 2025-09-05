# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import asyncio
from collections.abc import AsyncIterable
from enum import Enum
from typing import ClassVar

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.generic_scheduler._deferred_runner import (
    DeferredRunner,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    KeyNotFoundInHashError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    OperationName,
    ScheduleId,
    StepStatus,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._operation import (
    BaseStep,
    Operation,
    OperationRegistry,
    SingleStepGroup,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._store import (
    ScheduleDataStoreProxy,
    StepStoreProxy,
    Store,
    get_store,
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
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def store(app: FastAPI) -> Store:
    return get_store(app)


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


async def _assert_finshed_with_status(
    step_proxy: StepStoreProxy, expected_status: StepStatus
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        reraise=True,
        retry=retry_if_exception_type((AssertionError, KeyNotFoundInHashError)),
    ):
        with attempt:
            assert await step_proxy.get("status") == expected_status


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
    async def create(cls, app: FastAPI) -> None:
        _ = app
        _StepResultStore.set_result(cls.__name__, "created")

    @classmethod
    async def destroy(cls, app: FastAPI) -> None:
        _ = app
        _StepResultStore.set_result(cls.__name__, "destroyed")


class _StepFinisheError(BaseStep):
    @classmethod
    async def create(cls, app: FastAPI) -> None:
        _ = app
        _StepResultStore.set_result(cls.__name__, "created")
        msg = "I failed creating"
        raise RuntimeError(msg)

    @classmethod
    async def destroy(cls, app: FastAPI) -> None:
        _ = app
        _StepResultStore.set_result(cls.__name__, "destroyed")
        msg = "I failed destorying"
        raise RuntimeError(msg)


class _StepLongRunningToCancel(BaseStep):
    @classmethod
    async def create(cls, app: FastAPI) -> None:
        _ = app
        _StepResultStore.set_result(cls.__name__, "created")
        await asyncio.sleep(10000)

    @classmethod
    async def destroy(cls, app: FastAPI) -> None:
        _ = app
        _StepResultStore.set_result(cls.__name__, "destroyed")
        await asyncio.sleep(10000)


class _Action(str, Enum):
    DO_NOTHING = "NOTHING"
    CANCEL = "CANCEL"


@pytest.mark.parametrize(
    "operation, expected_step_status, action",
    [
        (
            [
                SingleStepGroup(_StepFinisheWithSuccess),
            ],
            StepStatus.SUCCESS,
            _Action.DO_NOTHING,
        ),
        (
            [
                SingleStepGroup(_StepFinisheError),
            ],
            StepStatus.FAILED,
            _Action.DO_NOTHING,
        ),
        (
            [
                SingleStepGroup(_StepLongRunningToCancel),
            ],
            StepStatus.CANCELLED,
            _Action.CANCEL,
        ),
    ],
)
@pytest.mark.parametrize("is_creating", [True, False])
async def test_something(
    registed_operation: None,
    store: Store,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    expected_step_status: StepStatus,
    is_creating: bool,
    action: _Action,
) -> None:

    # setup
    schedule_data_proxy = ScheduleDataStoreProxy(store=store, schedule_id=schedule_id)
    await schedule_data_proxy.set_multiple(
        {
            "operation_name": operation_name,
            "operation_context": {},
            "group_index": 0,
            "is_creating": is_creating,
        }
    )

    step_group = OperationRegistry.get_step_group(operation_name, 0)

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
        is_creating=is_creating,
    )

    ### tests starts here

    await DeferredRunner.start(
        schedule_id=schedule_id,
        operation_name=operation_name,
        step_group_name=step_group_name,
        step_name=step_name,
        is_creating=is_creating,
    )

    if action == _Action.CANCEL:
        await asyncio.sleep(0.2)  # give it some time to start

        task_uid = await step_proxy.get("deferred_task_uid")
        await DeferredRunner.cancel(task_uid)

    await _assert_finshed_with_status(step_proxy, expected_step_status)

    assert _StepResultStore.get_result(step.__name__) == (
        "created" if is_creating else "destroyed"
    )

    if expected_step_status == StepStatus.FAILED:
        error_traceback = await step_proxy.get("error_traceback")
        assert "I failed" in error_traceback
