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
from asyncpg import NoDataFoundError
from fastapi import FastAPI
from pydantic import NonNegativeFloat, NonNegativeInt, TypeAdapter
from pytest_simcore.helpers.dynamic_scheduler import (
    EXECUTED,
    REVERTED,
    BaseExpectedStepOrder,
    ExecuteRandom,
    ExecuteSequence,
    RevertRandom,
    RevertSequence,
    ensure_expected_order,
    ensure_keys_in_store,
)
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
    StepStoreProxy,
    cancel_operation,
    get_operation_name_or_none,
    restart_operation_step_stuck_during_revert,
    restart_operation_step_stuck_in_manual_intervention_during_execute,
    start_operation,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._core import (
    Core,
    Store,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._deferred_runner import (
    StepGroupName,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._errors import (
    CannotCancelWhileWaitingForManualInterventionError,
    InitialOperationContextKeyNotAllowedError,
    OperationNotCancellableError,
    ProvidedOperationContextKeysAreMissingError,
    StepNameNotInCurrentGroupError,
    StepNotInErrorStateError,
    StepNotWaitingForManualInterventionError,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    OperationContext,
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
_PARALLEL_RESTARTS: Final[NonNegativeInt] = 5
_DEFERRED_FINALIZATION_TIMEOUT: Final[NonNegativeFloat] = 1.0


@pytest.fixture
def app_environment(
    disable_scheduler_lifespan: None,
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
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _STEPS_CALL_ORDER.append((cls.__name__, EXECUTED))

        return {
            **required_context,
            **{k: _CTX_VALUE for k in cls.get_execute_provides_context_keys()},
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
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().execute(app, required_context)
        msg = "always fails only on EXECUTE"
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


class _FailOnExecuteAndRevertBS(_BS):
    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().execute(app, required_context)
        msg = "always fails on EXECUTE"
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
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().execute(app, required_context)
        await asyncio.sleep(1e10)


class _WaitManualInerventionBS(_BS):
    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        await super().execute(app, required_context)
        if _GlobalStepIssueTracker.has_issue:
            msg = "sometimes fails only on EXECUTE"
            raise RuntimeError(msg)

    @classmethod
    def wait_for_manual_intervention(cls) -> bool:
        return True


def _get_steps_matching_class(
    operation: Operation, *, match: type[BaseStep]
) -> list[type]:
    return [
        step
        for group in operation.step_groups
        for step in group.get_step_subgroup_to_run()
        if issubclass(step, match)
    ]


def _compose_key(
    key_nuber: int | None, *, with_revert: bool, is_executing: bool, is_providing: bool
) -> str:
    key_parts = [
        "bs",
        "revert" if with_revert else "",
        "e" if is_executing else "r",
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
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=False,
                is_executing=True,
                is_providing=False,
            )
        }

    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=False,
                is_executing=True,
                is_providing=True,
            )
        }


class _BaseRequiresProvidesRevertContext(_RevertBS, _MixingGetKeNumber):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_executing=True,
                is_providing=False,
            )
        }

    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_executing=True,
                is_providing=True,
            )
        }

    @classmethod
    def get_revert_requires_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_executing=False,
                is_providing=False,
            )
        }

    @classmethod
    def get_revert_provides_context_keys(cls) -> set[str]:
        return {
            _compose_key(
                cls.get_key_number(),
                with_revert=True,
                is_executing=False,
                is_providing=True,
            )
        }


async def _ensure_log_mesage(caplog: pytest.LogCaptureFixture, *, message: str) -> None:
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)  # wait for event to trigger
            assert message in caplog.text


async def _esnure_steps_have_status(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    *,
    step_group_name: StepGroupName,
    steps: Iterable[type[BaseStep]],
) -> None:
    store = Store.get_from_app_state(app)

    store_proxies = [
        StepStoreProxy(
            store=store,
            schedule_id=schedule_id,
            operation_name=operation_name,
            step_group_name=step_group_name,
            step_name=step.get_step_name(),
            is_executing=True,
        )
        for step in steps
    ]

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            for step_proxy in store_proxies:
                try:
                    await step_proxy.read("status")
                except NoDataFoundError:
                    msg = f"Step {step_proxy.step_name} has no status"
                    raise AssertionError(msg) from None


async def _ensure_one_step_in_manual_intervention(
    app: FastAPI,
    schedule_id: ScheduleId,
    operation_name: OperationName,
    *,
    step_group_name: StepGroupName,
    steps: Iterable[type[BaseStep]],
) -> None:
    store_proxies = [
        StepStoreProxy(
            store=Store.get_from_app_state(app),
            schedule_id=schedule_id,
            operation_name=operation_name,
            step_group_name=step_group_name,
            step_name=step.get_step_name(),
            is_executing=True,
        )
        for step in steps
    ]

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            reuires_intervention = False
            for proxy in store_proxies:
                try:
                    requires_manual_intervention = await proxy.read(
                        "requires_manual_intervention"
                    )
                    if requires_manual_intervention:
                        reuires_intervention = True
                        break
                except NoDataFoundError:
                    pass

            assert reuires_intervention is True


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


# Below fail on execute (expected)


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


# Below fail both on execute and revert (unexpected)


class _FCR1(_FailOnExecuteAndRevertBS): ...


class _FCR2(_FailOnExecuteAndRevertBS): ...


class _FCR3(_FailOnExecuteAndRevertBS): ...


# Below will sleep forever


class _SF1(_SleepsForeverBS): ...


class _SF2(_SleepsForeverBS): ...


# Below will wait for manual intervention after it fails on execute


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
            Operation(
                SingleStepGroup(_S1),
            ),
            [
                ExecuteSequence(_S1),
            ],
            id="s1",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(_S1, _S2),
            ),
            [
                ExecuteRandom(_S1, _S2),
            ],
            id="p2",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(_S1, _S2, _S3, _S4, _S5, _S6, _S7, _S8, _S9, _S10),
            ),
            [
                ExecuteRandom(_S1, _S2, _S3, _S4, _S5, _S6, _S7, _S8, _S9, _S10),
            ],
            id="p10",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                SingleStepGroup(_S2),
                SingleStepGroup(_S3),
                ParallelStepGroup(_S4, _S5, _S6, _S7, _S8, _S9),
                SingleStepGroup(_S10),
            ),
            [
                ExecuteSequence(_S1, _S2, _S3),
                ExecuteRandom(_S4, _S5, _S6, _S7, _S8, _S9),
                ExecuteSequence(_S10),
            ],
            id="s1-s1-s1-p6-s1",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_RS1),
            ),
            [
                ExecuteSequence(_RS1),
                RevertSequence(_RS1),
            ],
            id="s1(1r)",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(_RS1, _S1, _S2, _S3, _S4, _S5, _S6),
            ),
            [
                ExecuteRandom(_S1, _S2, _S3, _S4, _S5, _S6, _RS1),
                RevertRandom(_S1, _S2, _S3, _S4, _S5, _S6, _RS1),
            ],
            id="p7(1r)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4, _S5, _S6),
                SingleStepGroup(_RS1),
                SingleStepGroup(_S7),  # will not execute
                ParallelStepGroup(_S8, _S9),  # will not execute
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4, _S5, _S6),
                ExecuteSequence(_RS1),
                RevertSequence(_RS1),
                RevertRandom(_S2, _S3, _S4, _S5, _S6),
                RevertSequence(_S1),
            ],
            id="s1-p5-s1(1r)-s1-p2",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_RS1, _S2, _S3, _S4, _S5, _S6),
                SingleStepGroup(_S7),  # will not execute
                ParallelStepGroup(_S8, _S9),  # will not execute
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4, _S5, _S6, _RS1),
                RevertRandom(_S2, _S3, _S4, _S5, _S6, _RS1),
                RevertSequence(_S1),
            ],
            id="s1-p6(1r)-s1-p2",
        ),
        pytest.param(
            Operation(
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
            ),
            [
                ExecuteRandom(
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
async def test_execute_revert_order(
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    await ensure_expected_order(steps_call_order, expected_order)

    await ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order, expected_keys",
    [
        pytest.param(
            Operation(
                SingleStepGroup(_FCR1),
            ),
            [
                ExecuteSequence(_FCR1),
                RevertSequence(_FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:0S:R:_FCR1",
            },
            id="s1(1rf)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                SingleStepGroup(_FCR1),
            ),
            [
                ExecuteSequence(_S1, _FCR1),
                RevertSequence(_FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1S:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1S:E:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1S:R:_FCR1",
            },
            id="s2(1rf)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_FCR1, _S2, _S3),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _FCR1),
                RevertRandom(_S2, _S3, _FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:R:_S3",
            },
            id="s1p3(1rf)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_FCR1, _FCR2, _S2, _S3),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _FCR1, _FCR2),
                RevertRandom(_S2, _S3, _FCR2, _FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_FCR2",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S3",
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    await ensure_expected_order(steps_call_order, expected_order)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}
    await ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)


@pytest.mark.parametrize("cancel_count", [1, 10])
@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_before_cancel_order, expected_order",
    [
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                SingleStepGroup(_SF1),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteSequence(_SF1),
            ],
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteSequence(_SF1),
                RevertSequence(_SF1),
                RevertRandom(_S2, _S3, _S4),
                RevertSequence(_S1),
            ],
            id="s1p3s1(1sf)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4, _SF1, _SF2),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_SF1, _SF2, _S2, _S3, _S4),
            ],
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4, _SF1, _SF2),
                RevertRandom(_S2, _S3, _S4, _SF2, _SF1),
                RevertSequence(_S1),
            ],
            id="s1p5(2sf)",
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    await ensure_expected_order(steps_call_order, expected_before_cancel_order)

    # cancel in parallel multiple times (worst case)
    await asyncio.gather(
        *[cancel_operation(selected_app, schedule_id) for _ in range(cancel_count)]
    )

    await ensure_expected_order(steps_call_order, expected_order)

    await ensure_keys_in_store(selected_app, expected_keys=set())


_FAST_REPEAT_INTERVAL: Final[timedelta] = timedelta(seconds=0.1)
_REPAT_COUNT: Final[NonNegativeInt] = 10


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_before_cancel_order, expected_order",
    [
        pytest.param(
            Operation(
                SingleStepGroup(
                    _S1, repeat_steps=True, wait_before_repeat=_FAST_REPEAT_INTERVAL
                ),
            ),
            [ExecuteSequence(_S1) for _ in range(_REPAT_COUNT)],
            [
                *[ExecuteSequence(_S1) for _ in range(_REPAT_COUNT)],
                RevertSequence(_S1),
            ],
            id="s1(r)",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(
                    _S1,
                    _S2,
                    repeat_steps=True,
                    wait_before_repeat=_FAST_REPEAT_INTERVAL,
                ),
            ),
            [ExecuteRandom(_S1, _S2) for _ in range(_REPAT_COUNT)],
            [
                *[ExecuteRandom(_S1, _S2) for _ in range(_REPAT_COUNT)],
                RevertRandom(_S1, _S2),
            ],
            id="p2(r)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(
                    _RS1, repeat_steps=True, wait_before_repeat=_FAST_REPEAT_INTERVAL
                ),
            ),
            [ExecuteSequence(_RS1) for _ in range(_REPAT_COUNT)],
            [
                *[ExecuteSequence(_RS1) for _ in range(_REPAT_COUNT)],
                RevertSequence(_RS1),
            ],
            id="s1(rf)",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(
                    _RS1,
                    _RS2,
                    repeat_steps=True,
                    wait_before_repeat=_FAST_REPEAT_INTERVAL,
                ),
            ),
            [ExecuteRandom(_RS1, _RS2) for _ in range(_REPAT_COUNT)],
            [
                *[ExecuteRandom(_RS1, _RS2) for _ in range(_REPAT_COUNT)],
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    await ensure_expected_order(
        steps_call_order, expected_before_cancel_order, use_only_first_entries=True
    )

    # cancelling stops the loop and causes revert to run
    await cancel_operation(selected_app, schedule_id)

    await ensure_expected_order(
        steps_call_order, expected_order, use_only_last_entries=True
    )

    await ensure_keys_in_store(selected_app, expected_keys=set())


async def _wait_for_deferred_to_finalize() -> None:
    # give some time for background deferred to finish
    await asyncio.sleep(_DEFERRED_FINALIZATION_TIMEOUT)


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order, expected_keys, after_restart_expected_order",
    [
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                SingleStepGroup(_WMI1),
                # below are not included when waiting for manual intervention
                ParallelStepGroup(_S5, _S6),
                SingleStepGroup(_S7),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteSequence(_WMI1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:E",
                "SCH:{schedule_id}:GROUPS:test_op:2S:E",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2S:E:_WMI1",
            },
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteSequence(_WMI1),
                ExecuteSequence(_WMI1),  # retried step
                ExecuteRandom(_S5, _S6),  # it is completed now
                ExecuteSequence(_S7),  # it is completed now
            ],
            id="s1-p3-s1(1mi)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                ParallelStepGroup(_WMI1, _WMI2, _WMI3, _S5, _S6, _S7),
                # below are not included when waiting for manual intervention
                SingleStepGroup(_S8),
                ParallelStepGroup(_S9, _S10),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteRandom(_WMI1, _WMI2, _WMI3, _S5, _S6, _S7),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:E",
                "SCH:{schedule_id}:GROUPS:test_op:2P:E",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_S5",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_S6",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_S7",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_WMI1",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_WMI2",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_WMI3",
            },
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteRandom(_WMI1, _WMI2, _WMI3, _S5, _S6, _S7),
                ExecuteRandom(_WMI1, _WMI2, _WMI3),  # retried steps
                ExecuteSequence(_S8),  # it is completed now
                ExecuteRandom(_S9, _S10),  # it is completed now
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}

    await ensure_expected_order(steps_call_order, expected_order)

    await ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)

    group_index = len(expected_order) - 1
    step_group_name = operation.step_groups[group_index].get_step_group_name(
        index=group_index
    )
    await _esnure_steps_have_status(
        selected_app,
        schedule_id,
        operation_name,
        step_group_name=step_group_name,
        steps=expected_order[-1].steps,
    )
    await _wait_for_deferred_to_finalize()

    # even if cancelled, state of waiting for manual intervention remains the same
    await _ensure_one_step_in_manual_intervention(
        selected_app,
        schedule_id,
        operation_name,
        step_group_name=step_group_name,
        steps=expected_order[-1].steps,
    )
    with pytest.raises(CannotCancelWhileWaitingForManualInterventionError):
        await cancel_operation(selected_app, schedule_id)

    await ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)

    # set step to no longer raise and restart the failed steps
    steps_to_restart = _get_steps_matching_class(
        operation, match=_WaitManualInerventionBS
    )
    _GlobalStepIssueTracker.set_issue_solved()
    await limited_gather(
        *(
            restart_operation_step_stuck_in_manual_intervention_during_execute(
                selected_app, schedule_id, step.get_step_name()
            )
            for step in steps_to_restart
        ),
        limit=_PARALLEL_RESTARTS,
    )
    # should finish schedule operation
    await ensure_expected_order(steps_call_order, after_restart_expected_order)
    await ensure_keys_in_store(selected_app, expected_keys=set())


@pytest.mark.parametrize("app_count", [10])
async def test_operation_is_not_cancellable(
    reset_step_issue_tracker: None,
    preserve_caplog_for_async_logging: None,
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
    operation_name: OperationName,
):
    operation = Operation(SingleStepGroup(_S1), is_cancellable=False)
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})

    # even if cancelled, state of waiting for manual intervention remains the same
    with pytest.raises(OperationNotCancellableError):
        await cancel_operation(selected_app, schedule_id)


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, expected_order, expected_keys, after_restart_expected_order",
    [
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                SingleStepGroup(_FCR1),
                # below are not included in any expected order
                ParallelStepGroup(_S5, _S6),
                SingleStepGroup(_S7),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteSequence(_FCR1),
                RevertSequence(_FCR1),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:E",
                "SCH:{schedule_id}:GROUPS:test_op:2S:E",
                "SCH:{schedule_id}:GROUPS:test_op:2S:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2S:E:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:2S:R:_FCR1",
            },
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteSequence(_FCR1),
                RevertSequence(_FCR1),
                RevertSequence(_FCR1),  # this one is retried
                RevertRandom(_S2, _S3, _S4),
                RevertSequence(_S1),
            ],
            id="s1-p3-s1(1r)",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_S1),
                ParallelStepGroup(_S2, _S3, _S4),
                ParallelStepGroup(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
                # below are not included in any expected order
                SingleStepGroup(_S8),
                ParallelStepGroup(_S9, _S10),
            ),
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteRandom(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
                RevertRandom(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:1P:E",
                "SCH:{schedule_id}:GROUPS:test_op:2P:E",
                "SCH:{schedule_id}:GROUPS:test_op:2P:R",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_S1",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S2",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S3",
                "SCH:{schedule_id}:STEPS:test_op:1P:E:_S4",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_S5",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_S6",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_S7",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_FCR2",
                "SCH:{schedule_id}:STEPS:test_op:2P:E:_FCR3",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_S5",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_S6",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_S7",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_FCR1",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_FCR2",
                "SCH:{schedule_id}:STEPS:test_op:2P:R:_FCR3",
            },
            [
                ExecuteSequence(_S1),
                ExecuteRandom(_S2, _S3, _S4),
                ExecuteRandom(_FCR1, _FCR2, _FCR3, _S5, _S6, _S7),
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}

    await ensure_expected_order(steps_call_order, expected_order)
    await ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)

    await _esnure_steps_have_status(
        selected_app,
        schedule_id,
        operation_name,
        step_group_name=operation.step_groups[
            len(expected_order) - 2
        ].get_step_group_name(index=len(expected_order) - 2),
        steps=expected_order[-1].steps,
    )

    # set step to no longer raise and restart the failed steps
    steps_to_restart = _get_steps_matching_class(
        operation, match=_FailOnExecuteAndRevertBS
    )
    _GlobalStepIssueTracker.set_issue_solved()

    await _wait_for_deferred_to_finalize()
    await limited_gather(
        *(
            restart_operation_step_stuck_during_revert(
                selected_app, schedule_id, step.get_step_name()
            )
            for step in steps_to_restart
        ),
        limit=_PARALLEL_RESTARTS,
    )
    # should finish schedule operation
    await ensure_expected_order(steps_call_order, after_restart_expected_order)
    await ensure_keys_in_store(selected_app, expected_keys=set())


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
    operation = Operation(
        SingleStepGroup(_S1),
        ParallelStepGroup(_S2, _S3, _S4),
        ParallelStepGroup(_SF1, _FCR1),  # sleeps here forever
    )
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    await ensure_expected_order(
        steps_call_order,
        [
            ExecuteSequence(_S1),
            ExecuteRandom(_S2, _S3, _S4),
            ExecuteRandom(_SF1, _FCR1),
        ],
    )

    await _esnure_steps_have_status(
        selected_app,
        schedule_id,
        operation_name,
        step_group_name=operation.step_groups[2].get_step_group_name(index=2),
        steps=operation.step_groups[-1].steps,
    )

    with pytest.raises(StepNameNotInCurrentGroupError):
        await Core.get_from_app_state(
            selected_app
        ).restart_operation_step_stuck_in_error(
            schedule_id,
            _S5.get_step_name(),
            in_manual_intervention=in_manual_intervention,
        )

    with pytest.raises(StepNotInErrorStateError):
        await Core.get_from_app_state(
            selected_app
        ).restart_operation_step_stuck_in_error(
            schedule_id,
            _SF1.get_step_name(),
            in_manual_intervention=in_manual_intervention,
        )

    if not in_manual_intervention:
        # force restart of step as it would be in manual intervention
        # this is not allowed
        await _wait_for_deferred_to_finalize()
        with pytest.raises(StepNotWaitingForManualInterventionError):
            await Core.get_from_app_state(
                selected_app
            ).restart_operation_step_stuck_in_error(
                schedule_id,
                _FCR1.get_step_name(),
                in_manual_intervention=True,
            )


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, initial_context, expected_order",
    [
        pytest.param(
            Operation(
                SingleStepGroup(RPCtxS1),
            ),
            {
                "bs__e_req_1": _CTX_VALUE,  # required by execute
            },
            [
                ExecuteSequence(RPCtxS1),
            ],
            id="s1",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(RPCtxS1, RPCtxS2),
            ),
            {
                "bs__e_req_1": _CTX_VALUE,  # required by execute
                "bs__e_req_2": _CTX_VALUE,  # required by execute
            },
            [
                ExecuteRandom(RPCtxS1, RPCtxS2),
            ],
            id="p2",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(RPCtxR1),
            ),
            {
                "bs_revert_e_req_1": _CTX_VALUE,  # required by execute
                "bs_revert_r_req_1": _CTX_VALUE,  # not executed automatically since crete fails
            },
            [
                ExecuteSequence(RPCtxR1),
                RevertSequence(RPCtxR1),
            ],
            id="s1(1r)",
        ),
        pytest.param(
            Operation(
                ParallelStepGroup(RPCtxR1, RPCtxR2),
            ),
            {
                "bs_revert_e_req_1": _CTX_VALUE,  # required by execute
                "bs_revert_e_req_2": _CTX_VALUE,  # required by execute
                "bs_revert_r_req_1": _CTX_VALUE,  # not executed automatically since crete fails
                "bs_revert_r_req_2": _CTX_VALUE,  # not executed automatically since crete fails
            },
            [
                ExecuteRandom(RPCtxR1, RPCtxR2),
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    # NOTE: might fail because it raised ProvidedOperationContextKeysAreMissingError check logs
    await ensure_expected_order(steps_call_order, expected_order)

    await ensure_keys_in_store(selected_app, expected_keys=set())

    assert f"{ProvidedOperationContextKeysAreMissingError.__name__}" not in caplog.text


@pytest.mark.parametrize("app_count", [10])
@pytest.mark.parametrize(
    "operation, initial_context",
    [
        pytest.param(
            Operation(
                SingleStepGroup(RPCtxS1),
            ),
            {
                "bs__e_prov_1": _CTX_VALUE,  # already provied by step execute issue
            },
            id="s1",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(RPCtxR1),
            ),
            {
                "bs_revert_e_prov_1": _CTX_VALUE,  # already provied by step execute issue
            },
            id="s1",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(RPCtxR1),
            ),
            {
                "bs_revert_r_prov_1": _CTX_VALUE,  # already provied by step execute issue
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

    await ensure_keys_in_store(selected_app, expected_keys=set())


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

    # EXECUTE

    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"to_return", "trigger_revert"}

    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {"a_key"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        print("INJECTED_CONTEXT_C", required_context)
        _ = app
        _STEPS_CALL_ORDER.append((cls.__name__, EXECUTED))

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
            Operation(
                SingleStepGroup(_BadImplementedStep),
            ),
            {
                "trigger_revert": False,
                "to_return": {
                    "add_to_return": False,
                },
            },
            f"{ProvidedOperationContextKeysAreMissingError.__name__}: Provided context {{}} is missing keys {{'a_key'",
            [
                ExecuteSequence(_BadImplementedStep),
                RevertSequence(_BadImplementedStep),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_BadImplementedStep",
                "SCH:{schedule_id}:STEPS:test_op:0S:R:_BadImplementedStep",
            },
            id="execute-does-not-set-the-key-to-return",
        ),
        pytest.param(
            Operation(
                SingleStepGroup(_BadImplementedStep),
            ),
            {
                "trigger_revert": True,
                "to_return": {
                    "add_to_return": False,
                },
            },
            f"{ProvidedOperationContextKeysAreMissingError.__name__}: Provided context {{}} is missing keys {{'a_key'",
            [
                ExecuteSequence(_BadImplementedStep),
                RevertSequence(_BadImplementedStep),
            ],
            {
                "SCH:{schedule_id}",
                "SCH:{schedule_id}:GROUPS:test_op:0S:E",
                "SCH:{schedule_id}:GROUPS:test_op:0S:R",
                "SCH:{schedule_id}:OP_CTX:test_op",
                "SCH:{schedule_id}:STEPS:test_op:0S:E:_BadImplementedStep",
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
    assert TypeAdapter(ScheduleId).validate_python(schedule_id)

    await _ensure_log_mesage(caplog, message=expected_error_str)

    await ensure_expected_order(steps_call_order, expected_order)

    formatted_expected_keys = {k.format(schedule_id=schedule_id) for k in expected_keys}
    await ensure_keys_in_store(selected_app, expected_keys=formatted_expected_keys)


@pytest.mark.parametrize("app_count", [10])
async def test_get_operation_name_or_none(
    preserve_caplog_for_async_logging: None,
    operation_name: OperationName,
    selected_app: FastAPI,
    register_operation: Callable[[OperationName, Operation], None],
):
    assert (
        await get_operation_name_or_none(selected_app, "non_existing_schedule_id")
        is None
    )

    operation = Operation(SingleStepGroup(_S1))
    register_operation(operation_name, operation)

    schedule_id = await start_operation(selected_app, operation_name, {})

    assert await get_operation_name_or_none(selected_app, schedule_id) == operation_name
