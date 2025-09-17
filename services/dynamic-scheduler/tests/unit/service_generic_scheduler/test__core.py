# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from contextlib import AsyncExitStack
from copy import deepcopy
from datetime import timedelta
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
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    CannotCancelWhileWaitingForManualInterventionError,
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


@pytest.fixture
def operation_name() -> OperationName:
    return "test_op"


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
        msg = "always fails only on CREATE"
        raise RuntimeError(msg)


class _FailOnCreateAndRevertBS(_BS):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().create(app, required_context)
        msg = "always fails on CREATE"
        raise RuntimeError(msg)

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().revert(app, required_context)
        msg = "always fails on REVERT"
        raise RuntimeError(msg)


class _SleepsForeverBS(_BS):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().create(app, required_context)
        await asyncio.sleep(1e10)


class _WaitManualInerventionBS(_RevertBS):
    @classmethod
    def wait_for_manual_intervention(cls) -> bool:
        return True


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


def _asseert_expected_order(
    steps_call_order: list[tuple[str, str]],
    expected_order: list[_BaseExpectedStepOrder],
    *,
    use_only_first_entries: bool,
    use_only_last_entries: bool,
) -> None:
    assert not (use_only_first_entries and use_only_last_entries)

    expected_order_length = sum(len(x) for x in expected_order)

    # below operations are destructive make a copy
    call_order = deepcopy(steps_call_order)

    if use_only_first_entries:
        call_order = call_order[:expected_order_length]
    if use_only_last_entries:
        call_order = call_order[-expected_order_length:]

    assert len(call_order) == expected_order_length

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


async def _ensure_expected_order(
    steps_call_order: list[tuple[str, str]],
    expected_order: list[_BaseExpectedStepOrder],
    *,
    use_only_first_entries: bool = False,
    use_only_last_entries: bool = False,
) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)  # wait for envet to trigger
            _asseert_expected_order(
                steps_call_order,
                expected_order,
                use_only_first_entries=use_only_first_entries,
                use_only_last_entries=use_only_last_entries,
            )


async def _assert_keys_in_store(app: FastAPI, *, expected_keys: set[str]) -> None:
    keys = set(await get_store(app).redis.keys())
    assert keys == expected_keys


async def _ensure_keys_in_store(app: FastAPI, *, expected_keys: set[str]) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await _assert_keys_in_store(app, expected_keys=expected_keys)


############## TESTS ##############


# Below always succeed (expected)


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


# Below fail on create (expected)


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


# Below fail both on create and revert (unexpected)


class _FCR1(_FailOnCreateAndRevertBS): ...


class _FCR2(_FailOnCreateAndRevertBS): ...


# Below will sleep forever


class _SF1(_SleepsForeverBS): ...


class _SF2(_SleepsForeverBS): ...


# Below will wait for manual intervention after it fails on create


class _WMI1(_WaitManualInerventionBS): ...


class _WMI2(_WaitManualInerventionBS): ...


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
async def test_create_revert_order(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    expected_order: list[_BaseExpectedStepOrder],
):
    register_operation(operation_name, operation)

    schedule_id = await get_core(selected_app).create(operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await _ensure_expected_order(steps_call_order, expected_order)

    await _ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order, expected_keys",
    [
        pytest.param(
            [
                SingleStepGroup(_FCR1),
            ],
            [
                _CreateSequence(_FCR1),
                _RevertSequence(_FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:0S:R:_FCR1",
            },
            id="s1(1rf)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                SingleStepGroup(_FCR1),
            ],
            [
                _CreateSequence(_S1, _FCR1),
                _RevertSequence(_FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1S:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1S:C:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1S:R:_FCR1",
            },
            id="s2(1rf)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_FCR1, _S2, _S3),
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _FCR1),
                _RevertRandom(_S2, _S3, _FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_S3",
            },
            id="s1p3(1rf)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_FCR1, _FCR2, _S2, _S3),
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _FCR1, _FCR2),
                _RevertRandom(_S2, _S3, _FCR2, _FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_FCR2",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_FCR2",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_S3",
            },
            id="s1p4(2rf)",
        ),
    ],
)
async def test_fails_during_revert_is_in_error_state(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    expected_order: list[_BaseExpectedStepOrder],
    expected_keys: set[str],
):
    register_operation(operation_name, operation)

    schedule_id = await get_core(selected_app).create(operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await _ensure_expected_order(steps_call_order, expected_order)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}
    await _ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)


@pytest.mark.parametrize("cancel_count", [1, 10])
@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_before_cancel_order, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                SingleStepGroup(_SF1),
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _S4),
                _CreateSequence(_SF1),
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _S4),
                _CreateSequence(_SF1),
                _RevertSequence(_SF1),
                _RevertRandom(_S2, _S3, _S4),
                _RevertSequence(_S1),
            ],
            id="s1p3s1(1s)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4, _SF1, _SF2),
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_SF1, _SF2, _S2, _S3, _S4),
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _S4, _SF1, _SF2),
                _RevertRandom(_S2, _S3, _S4, _SF2, _SF1),
                _RevertSequence(_S1),
            ],
            id="s1p4(1s)",
        ),
    ],
)
async def test_cancelled_finishes_nicely(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    expected_before_cancel_order: list[_BaseExpectedStepOrder],
    expected_order: list[_BaseExpectedStepOrder],
    cancel_count: NonNegativeInt,
):
    register_operation(operation_name, operation)

    core = get_core(selected_app)
    schedule_id = await core.create(operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await _ensure_expected_order(steps_call_order, expected_before_cancel_order)

    # cancel in parallel multiple times (worst case)
    await asyncio.gather(
        *[core.cancel_schedule(schedule_id) for _ in range(cancel_count)]
    )

    await _ensure_expected_order(steps_call_order, expected_order)

    await _ensure_keys_in_store(selected_app, expected_keys=set())


_FAST_REPEAT_INTERVAL: Final[timedelta] = timedelta(seconds=0.1)
_REPAT_COUNT: Final[NonNegativeInt] = 10


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_before_cancel_order, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(
                    _S1, repeat_steps=True, wait_before_repeat=_FAST_REPEAT_INTERVAL
                ),
            ],
            [_CreateSequence(_S1) for _ in range(_REPAT_COUNT)],
            [
                *[_CreateSequence(_S1) for _ in range(_REPAT_COUNT)],
                _RevertSequence(_S1),
            ],
            id="s1(r)",
        ),
        pytest.param(
            [
                ParallelStepGroup(
                    _S1,
                    _S2,
                    repeat_steps=True,
                    wait_before_repeat=_FAST_REPEAT_INTERVAL,
                ),
            ],
            [_CreateRandom(_S1, _S2) for _ in range(_REPAT_COUNT)],
            [
                *[_CreateRandom(_S1, _S2) for _ in range(_REPAT_COUNT)],
                _RevertRandom(_S1, _S2),
            ],
            id="p2(r)",
        ),
        pytest.param(
            [
                SingleStepGroup(
                    _RS1, repeat_steps=True, wait_before_repeat=_FAST_REPEAT_INTERVAL
                ),
            ],
            [_CreateSequence(_RS1) for _ in range(_REPAT_COUNT)],
            [
                *[_CreateSequence(_RS1) for _ in range(_REPAT_COUNT)],
                _RevertSequence(_RS1),
            ],
            id="s1(rf)",
        ),
        pytest.param(
            [
                ParallelStepGroup(
                    _RS1,
                    _RS2,
                    repeat_steps=True,
                    wait_before_repeat=_FAST_REPEAT_INTERVAL,
                ),
            ],
            [_CreateRandom(_RS1, _RS2) for _ in range(_REPAT_COUNT)],
            [
                *[_CreateRandom(_RS1, _RS2) for _ in range(_REPAT_COUNT)],
                _RevertRandom(_RS1, _RS2),
            ],
            id="p2(rf)",
        ),
    ],
)
async def test_repeating_step(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    expected_before_cancel_order: list[_BaseExpectedStepOrder],
    expected_order: list[_BaseExpectedStepOrder],
):
    register_operation(operation_name, operation)

    core = get_core(selected_app)
    schedule_id = await core.create(operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await _ensure_expected_order(
        steps_call_order, expected_before_cancel_order, use_only_first_entries=True
    )

    # cancelling stops the loop and causes revert to run
    await core.cancel_schedule(schedule_id)

    await _ensure_expected_order(
        steps_call_order, expected_order, use_only_last_entries=True
    )

    await _ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order, expected_keys",
    [
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                SingleStepGroup(_WMI1),
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _S4),
                _CreateSequence(_WMI1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:C",
                "SCH:{schedule_id}:GROUPS:test_op:2S:C",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2S:C:_WMI1",
            },
            id="s1-p3-s1(1mi)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                ParallelStepGroup(_WMI1, _WMI2, _S5, _S6, _S7),
                SingleStepGroup(_S8),  # will be ignored
                ParallelStepGroup(_S9, _S10),  # will be ignored
            ],
            [
                _CreateSequence(_S1),
                _CreateRandom(_S2, _S3, _S4),
                _CreateRandom(_WMI1, _WMI2, _S5, _S6, _S7),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:C",
                "SCH:{schedule_id}:GROUPS:test_op:2P:C",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_S5",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_S6",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_S7",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_WMI1",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_WMI2",
            },
            id="s1-p3-p5(2mi)",
        ),
    ],
)
async def test_wait_for_manual_intervention(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    expected_order: list[_BaseExpectedStepOrder],
    expected_keys: set[str],
):
    register_operation(operation_name, operation)

    core = get_core(selected_app)
    schedule_id = await core.create(operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}

    await _ensure_expected_order(steps_call_order, expected_order)

    await _ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)

    # even if cancelled, state of waiting for manual intervention remains the same
    with pytest.raises(CannotCancelWhileWaitingForManualInterventionError):
        await core.cancel_schedule(schedule_id)
    # give some time for a "possible cancellation" to be processed
    await asyncio.sleep(0.1)
    await _ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)


# TODO: test something with initial_operation_context that requires data from a previous step,
#   we need a way to express that -> maybe limit a step to emit something in
#   the context if it already exists

# TODO: inital key already present in operation InitialOperationContextKeyNotAllowedError
# TODO: test for OperationContextValueIsNoneError (we can only test the ones retruned)
# TODO: add a test check for proper context usage from step to step and also for the initial_step context usage


# TODO: tests to make sure all this still works with interruptions! -> Redis restart or Rabbit restart
