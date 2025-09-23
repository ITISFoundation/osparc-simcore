# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument

import asyncio
import logging
import re
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable
from contextlib import AsyncExitStack
from datetime import timedelta
from secrets import choice
from typing import Any, Final

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pydantic import NonNegativeInt
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.utils import limited_gather
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.services.generic_scheduler import (
    BaseStep,
    Operation,
    OperationName,
    ParallelStepGroup,
    ProvidedOperationContext,
    RequiredOperationContext,
    ScheduleId,
    SingleStepGroup,
    cancel_operation,
    restart_operation_stuck_in_error_during_revert,
    restart_operation_sutck_in_manual_intervention_during_create,
    start_operation,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._core import get_core
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    CannotCancelWhileWaitingForManualInterventionError,
    InitialOperationContextKeyNotAllowedError,
    OperationContextValueIsNoneError,
    ProvidedOperationContextKeysAreMissingError,
    StepNameNotInCurrentGroupError,
    StepNotInErrorStateError,
    StepNotWaitingForManualInterventionError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    OperationContext,
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
from utils import (
    CREATED,
    REVERTED,
    BaseExpectedStepOrder,
    CreateRandom,
    CreateSequence,
    RevertRandom,
    RevertSequence,
    ensure_expected_order,
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
_PARALLEL_RESTARTS: Final[NonNegativeInt] = 5


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
def operation_name() -> OperationName:
    return "test_op"


_STEPS_CALL_ORDER: list[tuple[str, str]] = []


@pytest.fixture
def steps_call_order() -> Iterable[list[tuple[str, str]]]:
    _STEPS_CALL_ORDER.clear()
    yield _STEPS_CALL_ORDER
    _STEPS_CALL_ORDER.clear()


class _BS(BaseStep):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _STEPS_CALL_ORDER.append((cls.__name__, CREATED))

        return {
            **required_context,
            **{k: _CTX_VALUE for k in cls.get_create_provides_context_keys()},
        }

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _STEPS_CALL_ORDER.append((cls.__name__, REVERTED))

        return {
            **required_context,
            **{k: _CTX_VALUE for k in cls.get_revert_provides_context_keys()},
        }


class _RevertBS(_BS):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().create(app, required_context)
        msg = "always fails only on CREATE"
        raise RuntimeError(msg)


class _GlobalStepIssueTracker:
    has_issue: bool = True

    @classmethod
    def set_issue_solved(cls) -> None:
        cls.has_issue = False


@pytest.fixture
def reset_step_issue_tracker() -> Iterable[None]:
    _GlobalStepIssueTracker.has_issue = True
    yield
    _GlobalStepIssueTracker.has_issue = True


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
        if _GlobalStepIssueTracker.has_issue:
            msg = "sometimes fails only on REVERT"
            raise RuntimeError(msg)


class _SleepsForeverBS(_BS):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().create(app, required_context)
        await asyncio.sleep(1e10)


class _WaitManualInerventionBS(_BS):
    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().create(app, required_context)
        if _GlobalStepIssueTracker.has_issue:
            msg = "sometimes fails only on CREATE"
            raise RuntimeError(msg)

    @classmethod
    def wait_for_manual_intervention(cls) -> bool:
        return True


def _get_steps_matching_class(
    operation: Operation, *, match: type[BaseStep]
) -> list[type]:
    return [
        step
        for group in operation
        for step in group.get_step_subgroup_to_run()
        if issubclass(step, match)
    ]


def _compose_key(
    key_nuber: int | None, *, with_revert: bool, is_creating: bool, is_providing: bool
) -> str:
    key_parts = [
        "bs",
        "revert" if with_revert else "",
        "c" if is_creating else "r",
        "prov" if is_providing else "req",
        f"{key_nuber}",
    ]
    return "_".join(key_parts)


_CTX_VALUE: Final[str] = "a_value"


class _MixingGetKeNumber:
    @classmethod
    def get_key_number(cls) -> int:
        # key number if fetched form the calss name as the last digits or 0
        key_number: int = 0
        match = re.search(r"(\d+)\D*$", cls.__name__)
        if match:
            key_number = int(match.group(1))
        return key_number


class _BaseRequiresProvidesContext(_BS, _MixingGetKeNumber):
    @classmethod
    def get_create_requires_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=False,
                is_creating=True,
                is_providing=False,
            )
        }

    @classmethod
    def get_create_provides_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=False,
                is_creating=True,
                is_providing=True,
            )
        }


class _BaseRequiresProvidesRevertContext(_RevertBS, _MixingGetKeNumber):
    @classmethod
    def get_create_requires_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_creating=True,
                is_providing=False,
            )
        }

    @classmethod
    def get_create_provides_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_creating=True,
                is_providing=True,
            )
        }

    @classmethod
    def get_revert_requires_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_creating=False,
                is_providing=False,
            )
        }

    @classmethod
    def get_revert_provides_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_creating=False,
                is_providing=True,
            )
        }


async def _assert_keys_in_store(app: FastAPI, *, expected_keys: set[str]) -> None:
    keys = set(await get_store(app).redis.keys())
    assert keys == expected_keys


async def _ensure_keys_in_store(app: FastAPI, *, expected_keys: set[str]) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await _assert_keys_in_store(app, expected_keys=expected_keys)


async def _esnure_log_mesage(caplog: pytest.LogCaptureFixture, *, message: str) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)  # wait for envet to trigger
            assert message in caplog.text


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


class _FCR3(_FailOnCreateAndRevertBS): ...


# Below will sleep forever


class _SF1(_SleepsForeverBS): ...


class _SF2(_SleepsForeverBS): ...


# Below will wait for manual intervention after it fails on create


class _WMI1(_WaitManualInerventionBS): ...


class _WMI2(_WaitManualInerventionBS): ...


class _WMI3(_WaitManualInerventionBS): ...


# Below steps which require and provide context keys


class RPCtxS1(_BaseRequiresProvidesContext): ...


class RPCtxS2(_BaseRequiresProvidesContext): ...


class RPCtxR1(_BaseRequiresProvidesRevertContext): ...


class RPCtxR2(_BaseRequiresProvidesRevertContext): ...


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(_S1),
            ],
            [
                CreateSequence(_S1),
            ],
            id="s1",
        ),
        pytest.param(
            [
                ParallelStepGroup(_S1, _S2),
            ],
            [
                CreateRandom(_S1, _S2),
            ],
            id="p2",
        ),
        pytest.param(
            [
                ParallelStepGroup(_S1, _S2, _S3, _S4, _S5, _S6, _S7, _S8, _S9, _S10),
            ],
            [
                CreateRandom(_S1, _S2, _S3, _S4, _S5, _S6, _S7, _S8, _S9, _S10),
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
                CreateSequence(_S1, _S2, _S3),
                CreateRandom(_S4, _S5, _S6, _S7, _S8, _S9),
                CreateSequence(_S10),
            ],
            id="s1-s1-s1-p6-s1",
        ),
        pytest.param(
            [
                SingleStepGroup(_RS1),
            ],
            [
                CreateSequence(_RS1),
                RevertSequence(_RS1),
            ],
            id="s1(1r)",
        ),
        pytest.param(
            [
                ParallelStepGroup(_RS1, _S1, _S2, _S3, _S4, _S5, _S6),
            ],
            [
                CreateRandom(_S1, _S2, _S3, _S4, _S5, _S6, _RS1),
                RevertRandom(_S1, _S2, _S3, _S4, _S5, _S6, _RS1),
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
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4, _S5, _S6),
                CreateSequence(_RS1),
                RevertSequence(_RS1),
                RevertRandom(_S2, _S3, _S4, _S5, _S6),
                RevertSequence(_S1),
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
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4, _S5, _S6, _RS1),
                RevertRandom(_S2, _S3, _S4, _S5, _S6, _RS1),
                RevertSequence(_S1),
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
                CreateRandom(
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
                RevertRandom(
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
    expected_order: list[BaseExpectedStepOrder],
):
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await ensure_expected_order(steps_call_order, expected_order)

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
                CreateSequence(_FCR1),
                RevertSequence(_FCR1),
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
                CreateSequence(_S1, _FCR1),
                RevertSequence(_FCR1),
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
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _FCR1),
                RevertRandom(_S2, _S3, _FCR1),
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
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _FCR1, _FCR2),
                RevertRandom(_S2, _S3, _FCR2, _FCR1),
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
    expected_order: list[BaseExpectedStepOrder],
    expected_keys: set[str],
):
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await ensure_expected_order(steps_call_order, expected_order)

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
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateSequence(_SF1),
            ],
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateSequence(_SF1),
                RevertSequence(_SF1),
                RevertRandom(_S2, _S3, _S4),
                RevertSequence(_S1),
            ],
            id="s1p3s1(1s)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4, _SF1, _SF2),
            ],
            [
                CreateSequence(_S1),
                CreateRandom(_SF1, _SF2, _S2, _S3, _S4),
            ],
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4, _SF1, _SF2),
                RevertRandom(_S2, _S3, _S4, _SF2, _SF1),
                RevertSequence(_S1),
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
    expected_before_cancel_order: list[BaseExpectedStepOrder],
    expected_order: list[BaseExpectedStepOrder],
    cancel_count: NonNegativeInt,
):
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await ensure_expected_order(steps_call_order, expected_before_cancel_order)

    # cancel in parallel multiple times (worst case)
    await asyncio.gather(
        *[cancel_operation(selected_app, schedule_id) for _ in range(cancel_count)]
    )

    await ensure_expected_order(steps_call_order, expected_order)

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
            [CreateSequence(_S1) for _ in range(_REPAT_COUNT)],
            [
                *[CreateSequence(_S1) for _ in range(_REPAT_COUNT)],
                RevertSequence(_S1),
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
            [CreateRandom(_S1, _S2) for _ in range(_REPAT_COUNT)],
            [
                *[CreateRandom(_S1, _S2) for _ in range(_REPAT_COUNT)],
                RevertRandom(_S1, _S2),
            ],
            id="p2(r)",
        ),
        pytest.param(
            [
                SingleStepGroup(
                    _RS1, repeat_steps=True, wait_before_repeat=_FAST_REPEAT_INTERVAL
                ),
            ],
            [CreateSequence(_RS1) for _ in range(_REPAT_COUNT)],
            [
                *[CreateSequence(_RS1) for _ in range(_REPAT_COUNT)],
                RevertSequence(_RS1),
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
            [CreateRandom(_RS1, _RS2) for _ in range(_REPAT_COUNT)],
            [
                *[CreateRandom(_RS1, _RS2) for _ in range(_REPAT_COUNT)],
                RevertRandom(_RS1, _RS2),
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
    expected_before_cancel_order: list[BaseExpectedStepOrder],
    expected_order: list[BaseExpectedStepOrder],
):
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await ensure_expected_order(
        steps_call_order, expected_before_cancel_order, use_only_first_entries=True
    )

    # cancelling stops the loop and causes revert to run
    await cancel_operation(selected_app, schedule_id)

    await ensure_expected_order(
        steps_call_order, expected_order, use_only_last_entries=True
    )

    await _ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order, expected_keys, after_restart_expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                SingleStepGroup(_WMI1),
                # below are not included when waiting for manual intervention
                ParallelStepGroup(_S5, _S6),
                SingleStepGroup(_S7),
            ],
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateSequence(_WMI1),
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
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateSequence(_WMI1),
                CreateSequence(_WMI1),  # retried step
                CreateRandom(_S5, _S6),  # it is completed now
                CreateSequence(_S7),  # it is completed now
            ],
            id="s1-p3-s1(1mi)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                ParallelStepGroup(_WMI1, _WMI2, _WMI3, _S5, _S6, _S7),
                # below are not included when waiting for manual intervention
                SingleStepGroup(_S8),
                ParallelStepGroup(_S9, _S10),
            ],
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateRandom(_WMI1, _WMI2, _WMI3, _S5, _S6, _S7),
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
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_WMI3",
            },
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateRandom(_WMI1, _WMI2, _WMI3, _S5, _S6, _S7),
                CreateRandom(_WMI1, _WMI2, _WMI3),  # retried steps
                CreateSequence(_S8),  # it is completed now
                CreateRandom(_S9, _S10),  # it is completed now
            ],
            id="s1-p3-p6(3mi)",
        ),
    ],
)
async def test_wait_for_manual_intervention(
    reset_step_issue_tracker: None,
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    expected_order: list[BaseExpectedStepOrder],
    expected_keys: set[str],
    after_restart_expected_order: list[BaseExpectedStepOrder],
):
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}

    await ensure_expected_order(steps_call_order, expected_order)

    await _ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)

    # even if cancelled, state of waiting for manual intervention remains the same
    with pytest.raises(CannotCancelWhileWaitingForManualInterventionError):
        await cancel_operation(selected_app, schedule_id)
    # give some time for a "possible cancellation" to be processed
    await asyncio.sleep(0.1)
    await _ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)

    # set step to no longer raise and restart the failed steps
    steps_to_restart = _get_steps_matching_class(
        operation, match=_WaitManualInerventionBS
    )
    _GlobalStepIssueTracker.set_issue_solved()
    await limited_gather(
        *(
            restart_operation_sutck_in_manual_intervention_during_create(
                selected_app, schedule_id, step.get_step_name()
            )
            for step in steps_to_restart
        ),
        limit=_PARALLEL_RESTARTS,
    )
    # should finish schedule operation
    await ensure_expected_order(steps_call_order, after_restart_expected_order)
    await _ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order, expected_keys, after_restart_expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                SingleStepGroup(_FCR1),
                # below are not included in any expected order
                ParallelStepGroup(_S5, _S6),
                SingleStepGroup(_S7),
            ],
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateSequence(_FCR1),
                RevertSequence(_FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:C",
                "SCH:{schedule_id}:GROUPS:test_op:2S:C",
                "SCH:{schedule_id}:GROUPS:test_op:2S:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2S:C:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:2S:R:_FCR1",
            },
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateSequence(_FCR1),
                RevertSequence(_FCR1),
                RevertSequence(_FCR1),  # this one is retried
                RevertRandom(_S2, _S3, _S4),
                RevertSequence(_S1),
            ],
            id="s1-p3-s1(1r)",
        ),
        pytest.param(
            [
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                ParallelStepGroup(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
                # below are not included in any expected order
                SingleStepGroup(_S8),
                ParallelStepGroup(_S9, _S10),
            ],
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateRandom(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
                RevertRandom(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:1P:C",
                "SCH:{schedule_id}:GROUPS:test_op:2P:C",
                "SCH:{schedule_id}:GROUPS:test_op:2P:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:C:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_S5",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_S6",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_S7",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_FCR2",
                "SCH:{schedule_id}:STEPS:test_op:2P:C:_FCR3",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_S5",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_S6",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_S7",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_FCR2",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_FCR3",
            },
            [
                CreateSequence(_S1),
                CreateRandom(_S2, _S3, _S4),
                CreateRandom(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
                RevertRandom(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
                RevertRandom(_FCR1, _FCR2, _FCR3),  # retried steps
                RevertRandom(_S2, _S3, _S4),
                RevertSequence(_S1),
            ],
            id="s1-p3-p6(3r)",
        ),
    ],
)
async def test_restart_revert_operation_step_in_error(
    reset_step_issue_tracker: None,
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    expected_order: list[BaseExpectedStepOrder],
    expected_keys: set[str],
    after_restart_expected_order: list[BaseExpectedStepOrder],
):
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}

    await ensure_expected_order(steps_call_order, expected_order)
    await _ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)

    # give some time for the deferred runner to store the errors
    # avoids flkayness
    await asyncio.sleep(0.1)

    # set step to no longer raise and restart the failed steps
    steps_to_restart = _get_steps_matching_class(
        operation, match=_FailOnCreateAndRevertBS
    )
    _GlobalStepIssueTracker.set_issue_solved()
    await limited_gather(
        *(
            restart_operation_stuck_in_error_during_revert(
                selected_app, schedule_id, step.get_step_name()
            )
            for step in steps_to_restart
        ),
        limit=_PARALLEL_RESTARTS,
    )
    # should finish schedule operation
    await ensure_expected_order(steps_call_order, after_restart_expected_order)
    await _ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize("in_manual_intervention", [True, False])
async def test_errors_with_restart_operation_step_in_error(
    preserve_caplog_for_async_logging: None,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation_name: OperationName,
    in_manual_intervention: bool,
):
    operation: Operation = [
        SingleStepGroup(_S1),
        ParallelStepGroup(_S2, _S3, _S4),
        ParallelStepGroup(_SF1, _FCR1),  # sleeps here forever
    ]
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert isinstance(schedule_id, ScheduleId)

    await ensure_expected_order(
        steps_call_order,
        [
            CreateSequence(_S1),
            CreateRandom(_S2, _S3, _S4),
            CreateRandom(_SF1, _FCR1),
        ],
    )
    # give some time for the deferred runner to store the errors
    await asyncio.sleep(0.1)

    with pytest.raises(StepNameNotInCurrentGroupError):
        await get_core(selected_app).restart_operation_step_stuck_in_error(
            schedule_id,
            _S5.get_step_name(),
            in_manual_intervention=in_manual_intervention,
        )

    with pytest.raises(StepNotInErrorStateError):
        await get_core(selected_app).restart_operation_step_stuck_in_error(
            schedule_id,
            _SF1.get_step_name(),
            in_manual_intervention=in_manual_intervention,
        )

    if not in_manual_intervention:
        # force restart of step as it would be in manual intervention
        # this is not allowed
        with pytest.raises(StepNotWaitingForManualInterventionError):
            await get_core(selected_app).restart_operation_step_stuck_in_error(
                schedule_id,
                _FCR1.get_step_name(),
                in_manual_intervention=True,
            )


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, initial_context, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(RPCtxS1),
            ],
            {
                "bs__c_req_1": _CTX_VALUE,  # required by create
            },
            [
                CreateSequence(RPCtxS1),
            ],
            id="s1",
        ),
        pytest.param(
            [
                ParallelStepGroup(RPCtxS1, RPCtxS2),
            ],
            {
                "bs__c_req_1": _CTX_VALUE,  # required by create
                "bs__c_req_2": _CTX_VALUE,  # required by create
            },
            [
                CreateRandom(RPCtxS1, RPCtxS2),
            ],
            id="p2",
        ),
        pytest.param(
            [
                SingleStepGroup(RPCtxR1),
            ],
            {
                "bs_revert_c_req_1": _CTX_VALUE,  # required by create
                "bs_revert_r_req_1": _CTX_VALUE,  # not created autmatically since crete fails
            },
            [
                CreateSequence(RPCtxR1),
                RevertSequence(RPCtxR1),
            ],
            id="s1(1r)",
        ),
        pytest.param(
            [
                ParallelStepGroup(RPCtxR1, RPCtxR2),
            ],
            {
                "bs_revert_c_req_1": _CTX_VALUE,  # required by create
                "bs_revert_c_req_2": _CTX_VALUE,  # required by create
                "bs_revert_r_req_1": _CTX_VALUE,  # not created autmatically since crete fails
                "bs_revert_r_req_2": _CTX_VALUE,  # not created autmatically since crete fails
            },
            [
                CreateRandom(RPCtxR1, RPCtxR2),
                RevertRandom(RPCtxR1, RPCtxR2),
            ],
            id="p2(2r)",
        ),
    ],
)
async def test_operation_context_usage(
    preserve_caplog_for_async_logging: None,
    caplog: pytest.LogCaptureFixture,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    initial_context: OperationContext,
    expected_order: list[BaseExpectedStepOrder],
):
    caplog.at_level(logging.DEBUG)
    caplog.clear()

    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, initial_context)
    assert isinstance(schedule_id, ScheduleId)

    # NOTE: might fail because it raised ProvidedOperationContextKeysAreMissingError check logs
    await ensure_expected_order(steps_call_order, expected_order)

    await _ensure_keys_in_store(selected_app, expected_keys=set())

    assert f"{OperationContextValueIsNoneError.__name__}" not in caplog.text
    assert f"{ProvidedOperationContextKeysAreMissingError.__name__}" not in caplog.text


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, initial_context",
    [
        pytest.param(
            [
                SingleStepGroup(RPCtxS1),
            ],
            {
                "bs__c_prov_1": _CTX_VALUE,  # already provied by step creates issue
            },
            id="s1",
        ),
        pytest.param(
            [
                SingleStepGroup(RPCtxR1),
            ],
            {
                "bs_revert_c_prov_1": _CTX_VALUE,  # already provied by step creates issue
            },
            id="s1",
        ),
        pytest.param(
            [
                SingleStepGroup(RPCtxR1),
            ],
            {
                "bs_revert_r_prov_1": _CTX_VALUE,  # already provied by step creates issue
            },
            id="s1",
        ),
    ],
)
async def test_operation_initial_context_using_key_provided_by_step(
    preserve_caplog_for_async_logging: None,
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    initial_context: OperationContext,
):
    register_operation(operation_name, operation)

    with pytest.raises(InitialOperationContextKeyNotAllowedError):
        await start_operation(selected_app, operation_name, initial_context)

    await _ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, initial_context, expected_order",
    [
        pytest.param(
            [
                SingleStepGroup(RPCtxS1),
            ],
            {
                # `bs__c_req_1` is missing
            },
            [
                RevertSequence(RPCtxS1),
            ],
            id="missing_context_key",
        ),
        pytest.param(
            [
                SingleStepGroup(RPCtxS1),
            ],
            {
                "bs__c_req_1": None,
            },
            [
                RevertSequence(RPCtxS1),
            ],
            id="context_key_is_none",
        ),
    ],
)
async def test_step_does_not_receive_context_key_or_is_none(
    preserve_caplog_for_async_logging: None,
    caplog: pytest.LogCaptureFixture,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    initial_context: OperationContext,
    expected_order: list[BaseExpectedStepOrder],
):
    caplog.at_level(logging.DEBUG)
    caplog.clear()

    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, initial_context)
    assert isinstance(schedule_id, ScheduleId)

    await _esnure_log_mesage(caplog, message=OperationContextValueIsNoneError.__name__)

    await ensure_expected_order(steps_call_order, expected_order)

    await _ensure_keys_in_store(selected_app, expected_keys=set())


class _BadImplementedStep(BaseStep):
    @classmethod
    def _get_provided_context(
        cls, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext:
        print("GOT", required_context)
        return_values = {}
        to_return = required_context["to_return"]
        if to_return["add_to_return"]:
            return_values.update(to_return["keys"])

        return return_values

    # CREATE

    @classmethod
    def get_create_requires_context_keys(cls) -> set[str]:
        return {"to_return", "trigger_revert"}

    @classmethod
    def get_create_provides_context_keys(cls) -> set[str]:
        return {"a_key"}

    @classmethod
    async def create(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        print("INJECTED_CONTEXT_C", required_context)
        _ = app
        _STEPS_CALL_ORDER.append((cls.__name__, CREATED))

        if required_context.get("trigger_revert"):
            msg = "triggering revert"
            raise RuntimeError(msg)

        return cls._get_provided_context(required_context)

    # REVERT

    @classmethod
    def get_revert_requires_context_keys(cls) -> set[str]:
        return {"to_return", "trigger_revert"}

    @classmethod
    def get_revert_provides_context_keys(cls) -> set[str]:
        return {"a_key"}

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        print("INJECTED_CONTEXT_R", required_context)
        _ = app
        _STEPS_CALL_ORDER.append((cls.__name__, REVERTED))

        return cls._get_provided_context(required_context)


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, initial_context, expected_error_str, expected_order, expected_keys",
    [
        pytest.param(
            [
                SingleStepGroup(_BadImplementedStep),
            ],
            {
                "trigger_revert": False,
                "to_return": {
                    "add_to_return": True,
                    "keys": {"a_key": None},
                },
            },
            f"{OperationContextValueIsNoneError.__name__}: Values of context cannot be None: {{'a_key'",
            [
                CreateSequence(_BadImplementedStep),
                RevertSequence(_BadImplementedStep),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_BadImplementedStep",
                "SCH:{schedule_id}:STEPS:test_op:0S:R:_BadImplementedStep",
            },
            id="create-returns-key-set-to-None",
        ),
        pytest.param(
            [
                SingleStepGroup(_BadImplementedStep),
            ],
            {
                "trigger_revert": False,
                "to_return": {
                    "add_to_return": False,
                },
            },
            f"{ProvidedOperationContextKeysAreMissingError.__name__}: Provided context {{}} is missing keys {{'a_key'",
            [
                CreateSequence(_BadImplementedStep),
                RevertSequence(_BadImplementedStep),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_BadImplementedStep",
                "SCH:{schedule_id}:STEPS:test_op:0S:R:_BadImplementedStep",
            },
            id="create-does-not-set-the-key-to-return",
        ),
        pytest.param(
            [
                SingleStepGroup(_BadImplementedStep),
            ],
            {
                "trigger_revert": True,
                "to_return": {
                    "add_to_return": True,
                    "keys": {"a_key": None},
                },
            },
            f"{OperationContextValueIsNoneError.__name__}: Values of context cannot be None: {{'a_key'",
            [
                CreateSequence(_BadImplementedStep),
                RevertSequence(_BadImplementedStep),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_BadImplementedStep",
                "SCH:{schedule_id}:STEPS:test_op:0S:R:_BadImplementedStep",
            },
            id="revert-returns-key-set-to-None",
        ),
        pytest.param(
            [
                SingleStepGroup(_BadImplementedStep),
            ],
            {
                "trigger_revert": True,
                "to_return": {
                    "add_to_return": False,
                },
            },
            f"{ProvidedOperationContextKeysAreMissingError.__name__}: Provided context {{}} is missing keys {{'a_key'",
            [
                CreateSequence(_BadImplementedStep),
                RevertSequence(_BadImplementedStep),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:C",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:STEPS:test_op:0S:C:_BadImplementedStep",
                "SCH:{schedule_id}:STEPS:test_op:0S:R:_BadImplementedStep",
            },
            id="revert-does-not-set-the-key-to-return",
        ),
    ],
)
async def test_step_does_not_provide_declared_key_or_is_none(
    preserve_caplog_for_async_logging: None,
    caplog: pytest.LogCaptureFixture,
    steps_call_order: list[tuple[str, str]],
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation: Operation,
    operation_name: OperationName,
    initial_context: OperationContext,
    expected_error_str: str,
    expected_order: list[BaseExpectedStepOrder],
    expected_keys: set[str],
):
    caplog.at_level(logging.DEBUG)
    caplog.clear()

    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, initial_context)
    assert isinstance(schedule_id, ScheduleId)

    await _esnure_log_mesage(caplog, message=expected_error_str)

    await ensure_expected_order(steps_call_order, expected_order)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}
    await _ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)
