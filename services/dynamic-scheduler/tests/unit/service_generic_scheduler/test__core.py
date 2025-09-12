# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from contextlib import AsyncExitStack
from copy import deepcopy
from secrets import choice
from typing import Final

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pydantic import NonNegativeInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.utils import limited_gather
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.services.generic_scheduler._core import (
    get_core,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    OperationContext,
    OperationName,
    ScheduleId,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._operation import (
    BaseStep,
    Operation,
    OperationRegistry,
    ParallelStepGroup,
    SingleStepGroup,
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

_PARALLEL_APP_CREATION: Final[NonNegativeInt] = 5


@pytest.fixture
def disable_other_generic_scheduler_modules(mocker: MockerFixture) -> None:
    # these also use redis
    generic_scheduler_module = (
        "simcore_service_dynamic_scheduler.services.generic_scheduler"
    )
    mocker.patch(f"{generic_scheduler_module}._store.lifespan")
    mocker.patch(f"{generic_scheduler_module}._core.lifespan")


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
async def get_app(
    app_environment: EnvVarsDict,
) -> AsyncIterable[Callable[[], Awaitable[FastAPI]]]:
    exit_stack = AsyncExitStack()

    started_apps: list[FastAPI] = []

    async def _() -> FastAPI:
        app = create_app()
        started_apps.append(app)

        await exit_stack.enter_async_context(LifespanManager(app))
        return app

    yield _

    await exit_stack.aclose()


@pytest.fixture
async def selected_app(
    get_app: Callable[[], Awaitable[FastAPI]], app_count: NonNegativeInt
) -> FastAPI:
    # initialize a bunch of apps and randomly select one
    # this will make sure that there is competition events catching possible issues
    apps: list[FastAPI] = await limited_gather(
        *[get_app() for _ in range(app_count)], limit=_PARALLEL_APP_CREATION
    )
    return choice(apps)


@pytest.fixture
def register_operation() -> Iterable[Callable[[OperationName, Operation], None]]:
    to_unregister: list[OperationName] = []

    def _(opration_name: OperationName, operation: Operation) -> None:
        OperationRegistry.register(opration_name, operation)
        to_unregister.append(opration_name)

    yield _

    for opration_name in to_unregister:
        OperationRegistry.unregister(opration_name)


_STEPS_CALL_ORDER: list[tuple[str, str]] = []


@pytest.fixture
def steps_call_order() -> Iterable[list[tuple[str, str]]]:
    yield _STEPS_CALL_ORDER
    _STEPS_CALL_ORDER.clear()


# UTILS ---------------------------------------------------------------

_CREATED: Final[str] = "create"
_REVERTED: Final[str] = "revert"


class _BS(BaseStep):
    @classmethod
    async def create(cls, app: FastAPI) -> None:
        _ = app
        _STEPS_CALL_ORDER.append((cls.__name__, _CREATED))

    @classmethod
    async def revert(cls, app: FastAPI) -> None:
        _ = app
        _STEPS_CALL_ORDER.append((cls.__name__, _REVERTED))


class _BaseExpectedStepOrder:
    def __init__(self, *steps: type[BaseStep]) -> None:
        self.steps = steps

    def __len__(self) -> int:
        return len(self.steps)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(step.get_step_name() for step in self.steps)})"


class _CreateSequence(_BaseExpectedStepOrder):
    """steps appear in a sequence as CREATE"""


class _CreateRandom(_BaseExpectedStepOrder):
    """steps appear in any given order as CREATE"""


class _RevertSequence(_BaseExpectedStepOrder):
    """steps appear in a sequence as REVERT"""


class _RevertRandom(_BaseExpectedStepOrder):
    """steps appear in any given order as REVERT"""


def _assert_sequence(
    remaning_call_order: list[tuple[str, str]],
    steps: tuple[type[BaseStep], ...],
    *,
    expected: str,
) -> None:
    for step in steps:
        step_name, actual = remaning_call_order.pop(0)
        assert step_name == step.get_step_name()
        assert actual == expected


def _assert_random(
    remaning_call_order: list[tuple[str, str]],
    steps: tuple[type[BaseStep], ...],
    *,
    expected: str,
) -> None:
    steps_names = {step.get_step_name() for step in steps}
    for _ in steps:
        step_name, actual = remaning_call_order.pop(0)
        assert step_name in steps_names
        assert actual == expected
        steps_names.remove(step_name)


def _asseert_order_as_expected(
    steps_call_order: list[tuple[str, str]],
    expected_order: list[_BaseExpectedStepOrder],
) -> None:
    # below operations are destructive make a copy
    call_order = deepcopy(steps_call_order)

    assert len(call_order) == sum(len(x) for x in expected_order)

    for group in expected_order:
        if isinstance(group, _CreateSequence):
            _assert_sequence(call_order, group.steps, expected=_CREATED)
        elif isinstance(group, _CreateRandom):
            _assert_random(call_order, group.steps, expected=_CREATED)
        elif isinstance(group, _RevertSequence):
            _assert_sequence(call_order, group.steps, expected=_REVERTED)
        elif isinstance(group, _RevertRandom):
            _assert_random(call_order, group.steps, expected=_REVERTED)
        else:
            msg = f"Unknown {group=}"
            raise NotImplementedError(msg)
    assert not call_order, f"Left overs {call_order=}"


# TESTS ---------------------------------------------------------------


class _S1(_BS): ...


class _S2(_BS): ...


class _S3(_BS): ...


class _S4(_BS): ...


class _S5(_BS): ...


class _S6(_BS): ...


class _S7(_BS): ...


class _S8(_BS): ...


class _S9(_BS): ...


class _S10(_BS): ...


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, operation_context, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(_S1),
            ],
            {},
            [
                _CreateSequence(_S1),
            ],
            id="s1",
        ),
        pytest.param(
            [
                ParallelStepGroup(_S1, _S2),
            ],
            {},
            [
                _CreateRandom(_S1, _S2),
            ],
            id="p2",
        ),
        pytest.param(
            [
                ParallelStepGroup(_S1, _S2, _S3, _S4, _S5, _S6, _S7, _S8, _S9, _S10),
            ],
            {},
            [
                _CreateRandom(_S1, _S2, _S3, _S4, _S5, _S6, _S7, _S8, _S9, _S10),
            ],
            id="p10",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                SingleStepGroup(_S2),
                SingleStepGroup(_S3),
                ParallelStepGroup(_S4, _S5, _S6, _S7, _S8, _S9),
                SingleStepGroup(_S10),
            ],
            {},
            [
                _CreateSequence(_S1, _S2, _S3),
                _CreateRandom(_S4, _S5, _S6, _S7, _S8, _S9),
                _CreateSequence(_S10),
            ],
            id="s1-s1-s1-p6-s1",
        ),
    ],
)
async def test_core_workflow(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_context: OperationContext,
    expected_order: list[_BaseExpectedStepOrder],
    faker: Faker,
):
    operation_name: OperationName = faker.uuid4()

    register_operation(operation_name, operation)

    schedule_id = await get_core(selected_app).create(operation_name, operation_context)
    assert isinstance(schedule_id, ScheduleId)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            await asyncio.sleep(0)  # wait for envet to trigger
            _asseert_order_as_expected(steps_call_order, expected_order)


# TODO: test reversal
# TODO: test manual intervention
# TODO: test repeating
