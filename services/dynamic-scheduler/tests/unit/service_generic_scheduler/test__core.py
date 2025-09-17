# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from contextlib import AsyncExitStack
from copy import deepcopy
from secrets import choice
from typing import Any, Final

import pytest
from asgi_lifespan import LifespanManager
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
    OperationName,
    ProvidedOperationContext,
    RequiredOperationContext,
    ScheduleId,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._operation import (
    BaseStep,
    Operation,
    OperationRegistry,
    ParallelStepGroup,
    SingleStepGroup,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._store import (
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


_RETRY_PARAMS: Final[dict[str, Any]] = {
    "wait": wait_fixed(0.1),
    "stop": stop_after_delay(5),
    "retry": retry_if_exception_type(AssertionError),
}


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


_CREATED: Final[str] = "create"
_REVERTED: Final[str] = "revert"


class _BS(BaseStep):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _STEPS_CALL_ORDER.append((cls.__name__, _CREATED))

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _STEPS_CALL_ORDER.append((cls.__name__, _REVERTED))


class _RevertBS(_BS):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().create(app, required_context)
        msg = "always triggers a revert action"
        raise RuntimeError(msg)


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


def _assert_order_sequence(
    remaning_call_order: list[tuple[str, str]],
    steps: tuple[type[BaseStep], ...],
    *,
    expected: str,
) -> None:
    for step in steps:
        step_name, actual = remaning_call_order.pop(0)
        assert step_name == step.get_step_name()
        assert actual == expected


def _assert_order_random(
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
            _assert_order_sequence(call_order, group.steps, expected=_CREATED)
        elif isinstance(group, _CreateRandom):
            _assert_order_random(call_order, group.steps, expected=_CREATED)
        elif isinstance(group, _RevertSequence):
            _assert_order_sequence(call_order, group.steps, expected=_REVERTED)
        elif isinstance(group, _RevertRandom):
            _assert_order_random(call_order, group.steps, expected=_REVERTED)
        else:
            msg = f"Unknown {group=}"
            raise NotImplementedError(msg)
    assert not call_order, f"Left overs {call_order=}"


async def _assert_keys_in_store(app: FastAPI, *, expected_keys: set[str]) -> None:
    keys = set(await get_store(app).redis.keys())
    assert keys == expected_keys


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


class _RS1(_RevertBS): ...


class _RS2(_RevertBS): ...


class _RS3(_RevertBS): ...


class _RS4(_RevertBS): ...


class _RS5(_RevertBS): ...


class _RS6(_RevertBS): ...


class _RS7(_RevertBS): ...


class _RS8(_RevertBS): ...


class _RS9(_RevertBS): ...


class _RS10(_RevertBS): ...


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(_S1),
            ],
            [
                _CreateSequence(_S1),
            ],
            id="s1",
        ),
        pytest.param(
            [
                ParallelStepGroup(_S1, _S2),
            ],
            [
                _CreateRandom(_S1, _S2),
            ],
            id="p2",
        ),
        pytest.param(
            [
                ParallelStepGroup(_S1, _S2, _S3, _S4, _S5, _S6, _S7, _S8, _S9, _S10),
            ],
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
            [
                _CreateSequence(_S1, _S2, _S3),
                _CreateRandom(_S4, _S5, _S6, _S7, _S8, _S9),
                _CreateSequence(_S10),
            ],
            id="s1-s1-s1-p6-s1",
        ),
        pytest.param(
            [
                SingleStepGroup(_RS1),
            ],
            [
                _CreateSequence(_RS1),
                _RevertSequence(_RS1),
            ],
            id="s1(1r)",
        ),
        pytest.param(
            [
                ParallelStepGroup(_RS1, _S1, _S2, _S3, _S4, _S5, _S6),
            ],
            [
                _CreateRandom(_S1, _S2, _S3, _S4, _S5, _S6, _RS1),
                _RevertRandom(_S1, _S2, _S3, _S4, _S5, _S6, _RS1),
            ],
            id="p7(1r)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4, _S5, _S6),
                SingleStepGroup(_RS1),
                SingleStepGroup(_S7),  # will not execute
                ParallelStepGroup(_S8, _S9),  # will not execute
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _S4, _S5, _S6),
                _CreateSequence(_RS1),
                _RevertSequence(_RS1),
                _RevertRandom(_S2, _S3, _S4, _S5, _S6),
                _RevertSequence(_S1),
            ],
            id="s1-p5-s1(1r)-s1-p2",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_RS1, _S2, _S3, _S4, _S5, _S6),
                SingleStepGroup(_S7),  # will not execute
                ParallelStepGroup(_S8, _S9),  # will not execute
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _S4, _S5, _S6, _RS1),
                _RevertRandom(_S2, _S3, _S4, _S5, _S6, _RS1),
                _RevertSequence(_S1),
            ],
            id="s1-p6(1r)-s1-p2",
        ),
        pytest.param(
            [
                ParallelStepGroup(
                    _S1,
                    _S2,
                    _S3,
                    _S4,
                    _S5,
                    _S6,
                    _S7,
                    _S8,
                    _S9,
                    _S10,
                    _RS1,
                    _RS2,
                    _RS3,
                    _RS4,
                    _RS5,
                    _RS6,
                    _RS7,
                    _RS8,
                    _RS9,
                    _RS10,
                ),
            ],
            [
                _CreateRandom(
                    _S1,
                    _S2,
                    _S3,
                    _S4,
                    _S5,
                    _S6,
                    _S7,
                    _S8,
                    _S9,
                    _S10,
                    _RS1,
                    _RS2,
                    _RS3,
                    _RS4,
                    _RS5,
                    _RS6,
                    _RS7,
                    _RS8,
                    _RS9,
                    _RS10,
                ),
                _RevertRandom(
                    _S1,
                    _S2,
                    _S3,
                    _S4,
                    _S5,
                    _S6,
                    _S7,
                    _S8,
                    _S9,
                    _S10,
                    _RS1,
                    _RS2,
                    _RS3,
                    _RS4,
                    _RS5,
                    _RS6,
                    _RS7,
                    _RS8,
                    _RS9,
                    _RS10,
                ),
            ],
            id="p20(10r)",
        ),
    ],
)
async def test_create_revert_workflow(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    expected_order: list[_BaseExpectedStepOrder],
):
    operation_name: OperationName = "test_op"

    register_operation(operation_name, operation)

    schedule_id = await get_core(selected_app).create(operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)  # wait for envet to trigger
            _asseert_order_as_expected(steps_call_order, expected_order)

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await _assert_keys_in_store(selected_app, expected_keys=set())


# TODO: test manual intervention

# TODO: test repeating: how do we stop this one? -> cancel it after a bit as it's supposed to run forever
# TODO: test fail on repating (what should happen?)
#   -> should continue like for the status, just logs error and repeats

# TODO: test something with initial_operation_context that requires data from a previous step,
#   we need a way to express that -> maybe limit a step to emit something in
#   the context if it already exists

# TODO: inital key already present in operation InitialOperationContextKeyNotAllowedError
# TODO: test for OperationContextValueIsNoneError (we can only test the ones retruned)
# TODO: add a test check for proper context usage from step to step and also for the initial_step context usage
