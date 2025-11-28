# pylint: disable=redefined-outer-name
# pylint: disable=too-many-instance-attributes
# pylint: disable=unused-argument
import asyncio
import logging
from asyncio import Event
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
from types import ModuleType
from typing import ClassVar, Final
from uuid import uuid4

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.dynamic_scheduler import (
    EXECUTED,
    REVERTED,
    BaseExpectedStepOrder,
    ExecuteSequence,
    RevertSequence,
    ensure_expected_order,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.deferred_tasks import DeferredContext
from servicelib.logging_utils import log_context
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.generic_scheduler import (
    BaseStep,
    ProvidedOperationContext,
    RequiredOperationContext,
    SingleStepGroup,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    OperationContext,
)
from simcore_service_dynamic_scheduler.services.scheduler import (
    start_service,
    stop_service,
)
from simcore_service_dynamic_scheduler.services.scheduler._operations import (
    legacy,
    new_style,
)

_logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "rabbit",
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


# UTILS

type _EventID = str


class _HaltEventTracker:
    """cannot store Event instances in Redis, keeping track in meory"""

    _EVENTS: ClassVar[dict[_EventID, Event]] = {}

    @classmethod
    def create_event(cls) -> _EventID:
        event_id = f"{uuid4()}"
        cls._EVENTS[event_id] = Event()
        return event_id

    @classmethod
    def get_event(cls, event_id: _EventID) -> Event:
        return cls._EVENTS[event_id]


def _get_key_execute(cls: type[BaseStep]) -> str:
    return f"{cls.__name__}_execute"


def _get_key_revert(cls: type[BaseStep]) -> str:
    return f"{cls.__name__}_revert"


@dataclass
class _Action:
    halt_event_id: _EventID | None = None
    fail: bool = False


_SLEEP_FOREVER: Final[NonNegativeFloat] = 1e6
_STEPS_CALL_ORDER: list[tuple[str, str]] = []


@pytest.fixture
def steps_call_order() -> Iterable[list[tuple[str, str]]]:
    _STEPS_CALL_ORDER.clear()
    yield _STEPS_CALL_ORDER
    _STEPS_CALL_ORDER.clear()


class _CoreBaseStep(BaseStep):
    @classmethod
    async def get_execute_wait_between_attempts(
        cls, context: DeferredContext
    ) -> timedelta:
        _ = context
        return timedelta(seconds=_SLEEP_FOREVER)

    @classmethod
    async def get_revert_wait_between_attempts(
        cls, context: DeferredContext
    ) -> timedelta:
        _ = context
        return timedelta(seconds=_SLEEP_FOREVER)

    @classmethod
    async def _execute_action(cls, app: FastAPI, action: _Action) -> None:
        _ = app
        with log_context(
            _logger, logging.DEBUG, f"step {cls.__name__} executing action {action=}"
        ):
            if action.fail:
                msg = f"Step {cls.__name__} failed as requested"
                raise RuntimeError(msg)

            if action.halt_event_id is not None:
                # allows to halt execution here and intercept when it ararives
                # at this point to trigger further actions
                event = _HaltEventTracker.get_event(action.halt_event_id)

                event.set()
                await asyncio.sleep(_SLEEP_FOREVER)

    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {_get_key_execute(cls)}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _STEPS_CALL_ORDER.append((cls.__name__, EXECUTED))

        action: dict = required_context[_get_key_execute(cls)]
        await cls._execute_action(app, _Action(**action))
        return None

    @classmethod
    def get_revert_requires_context_keys(cls) -> set[str]:
        return {_get_key_revert(cls)}

    @classmethod
    async def revert(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _STEPS_CALL_ORDER.append((cls.__name__, REVERTED))

        action: dict = required_context[_get_key_revert(cls)]
        await cls._execute_action(app, _Action(**action))
        return None


_DEFAULT_SLEEP_BEFORE_REPEAT: Final[timedelta] = timedelta(seconds=0.1)


class _LegacyStart(_CoreBaseStep): ...


class _LegacyMonitor(_CoreBaseStep):
    @classmethod
    def get_sleep_before_execute(cls) -> timedelta:
        """
        [optional] wait time before executing the step
        """
        return _DEFAULT_SLEEP_BEFORE_REPEAT


class _NewStyleStop(_CoreBaseStep): ...


class _NewStyleStart(_CoreBaseStep): ...


class _NewStyleMonitor(_CoreBaseStep):
    @classmethod
    def get_sleep_before_execute(cls) -> timedelta:
        """
        [optional] wait time before executing the step
        """
        return _DEFAULT_SLEEP_BEFORE_REPEAT


class _LegacyStop(_CoreBaseStep): ...


@dataclass
class _ProfileConfig:
    is_legacy: bool = False

    # START
    start_execute_halt: bool = False
    start_execute_fails: bool = False
    start_revert_halt: bool = False
    start_revert_fails: bool = False

    # MONITOR
    monitor_execute_halt: bool = False
    monitor_execute_fails: bool = False
    monitor_revert_halt: bool = False
    monitor_revert_fails: bool = False

    # STOP
    stop_execute_halt: bool = False
    stop_execute_fails: bool = False
    stop_revert_halt: bool = False
    stop_revert_fails: bool = False


@dataclass
class _HaltEvents:
    legacy_start_execute: Event
    legacy_start_revert: Event

    legacy_monitor_execute: Event
    legacy_monitor_revert: Event

    legacy_stop_execute: Event
    legacy_stop_revert: Event

    new_style_start_execute: Event
    new_style_start_revert: Event

    new_style_monitor_execute: Event
    new_style_monitor_revert: Event

    new_style_stop_execute: Event
    new_style_stop_revert: Event


def _create_action_data(*, register_event: bool, fail: bool) -> tuple[_Action, Event]:
    halt_event_id = _HaltEventTracker.create_event()
    action = _Action(halt_event_id=halt_event_id if register_event else None, fail=fail)

    halt_event = _HaltEventTracker.get_event(halt_event_id)
    return action, halt_event


def _get_context_and_events(
    config: _ProfileConfig,
) -> tuple[OperationContext, _HaltEvents]:
    initial_context: OperationContext = {}

    start = _LegacyStart if config.is_legacy else _NewStyleStart
    monitor = _LegacyMonitor if config.is_legacy else _NewStyleMonitor
    stop = _LegacyStop if config.is_legacy else _NewStyleStop

    # START
    action_start_execute, event_start_execute = _create_action_data(
        register_event=config.start_execute_halt, fail=config.start_execute_fails
    )
    initial_context[_get_key_execute(start)] = action_start_execute

    action_start_revert, event_start_revert = _create_action_data(
        register_event=config.start_revert_halt, fail=config.start_revert_fails
    )
    initial_context[_get_key_revert(start)] = action_start_revert

    # MONITOR
    action_monitor_execute, event_monitor_execute = _create_action_data(
        register_event=config.monitor_execute_halt,
        fail=config.monitor_execute_fails,
    )
    initial_context[_get_key_execute(monitor)] = action_monitor_execute
    action_monitor_revert, event_monitor_revert = _create_action_data(
        register_event=config.monitor_revert_halt,
        fail=config.monitor_revert_fails,
    )
    initial_context[_get_key_revert(monitor)] = action_monitor_revert

    # STOP
    action_stop_execute, event_stop_execute = _create_action_data(
        register_event=config.stop_execute_halt, fail=config.stop_execute_fails
    )
    initial_context[_get_key_execute(stop)] = action_stop_execute
    action_stop_revert, event_stop_revert = _create_action_data(
        register_event=config.stop_revert_halt, fail=config.stop_revert_fails
    )
    initial_context[_get_key_revert(stop)] = action_stop_revert

    halt_events = _HaltEvents(
        legacy_start_execute=event_start_execute,
        legacy_start_revert=event_start_revert,
        legacy_monitor_execute=event_monitor_execute,
        legacy_monitor_revert=event_monitor_revert,
        legacy_stop_execute=event_stop_execute,
        legacy_stop_revert=event_stop_revert,
        new_style_start_execute=event_start_execute,
        new_style_start_revert=event_start_revert,
        new_style_monitor_execute=event_monitor_execute,
        new_style_monitor_revert=event_monitor_revert,
        new_style_stop_execute=event_stop_execute,
        new_style_stop_revert=event_stop_revert,
    )

    return initial_context, halt_events


# MOCKS


@pytest.fixture
def mock_operations(mocker: MockerFixture) -> None:
    # replace all steps that do somthing in the operations with mocked ones
    # allows to simulate various testing scenarios while not impacting functionality

    def _replace_steps_in_operation(
        module: ModuleType, step_cls: type[BaseStep], *, is_monitor: bool = False
    ) -> None:
        mocker.patch.object(
            module, "_steps", new=[SingleStepGroup(step_cls, repeat_steps=is_monitor)]
        )

    _replace_steps_in_operation(legacy.start, _LegacyStart)
    _replace_steps_in_operation(legacy.monitor, _LegacyMonitor, is_monitor=True)
    _replace_steps_in_operation(legacy.stop, _LegacyStop)

    _replace_steps_in_operation(new_style.start, _NewStyleStart)
    _replace_steps_in_operation(new_style.monitor, _NewStyleMonitor, is_monitor=True)
    _replace_steps_in_operation(new_style.stop, _NewStyleStop)


@pytest.fixture
def inject_context_and_events(
    mocker: MockerFixture, profile_config: _ProfileConfig
) -> _HaltEvents:
    initial_context, halt_events = _get_context_and_events(profile_config)

    def _get_initial_context(node_id: NodeID) -> OperationContext:
        context = deepcopy(initial_context)
        context["node_id"] = node_id
        return context

    mocker.patch(
        "simcore_service_dynamic_scheduler.services.scheduler._operations.enforce._get_start_monitor_stop_initial_context",
        _get_initial_context,
    )

    return halt_events


@pytest.fixture
def halt_events(inject_context_and_events: _HaltEvents) -> _HaltEvents:
    return inject_context_and_events


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
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def start_data(node_id: NodeID) -> DynamicServiceStart:
    data = deepcopy(DynamicServiceStart.model_json_schema()["example"])
    data["service_uuid"] = node_id
    return TypeAdapter(DynamicServiceStart).validate_python(data)


@pytest.fixture
def stop_data(node_id: NodeID) -> DynamicServiceStop:
    data = deepcopy(DynamicServiceStop.model_json_schema()["example"])
    data["node_id"] = node_id
    return TypeAdapter(DynamicServiceStop).validate_python(data)


# TESTS


@pytest.mark.parametrize(
    "profile_config, expected_order_after_start, expected_order_after_stop",
    [
        pytest.param(
            _ProfileConfig(is_legacy=True),
            [
                ExecuteSequence(
                    _LegacyStart,
                    _LegacyMonitor,
                )
            ],
            [
                ExecuteSequence(_LegacyMonitor),
                RevertSequence(_LegacyMonitor),
                ExecuteSequence(_LegacyStop),
            ],
        ),
    ],
)
async def test_something(
    preserve_caplog_for_async_logging: None,
    mock_operations: None,
    halt_events: _HaltEvents,
    steps_call_order: list[tuple[str, str]],
    app: FastAPI,
    start_data: DynamicServiceStart,
    stop_data: DynamicServiceStop,
    expected_order_after_start: list[BaseExpectedStepOrder],
    expected_order_after_stop: list[BaseExpectedStepOrder],
) -> None:
    await start_service(app, start_data)
    await ensure_expected_order(
        steps_call_order, expected_order_after_start, use_only_first_entries=True
    )

    await stop_service(app, stop_data)
    await ensure_expected_order(
        steps_call_order, expected_order_after_stop, use_only_last_entries=True
    )


# - mock with something that can cause errors and problems
# - we want very faulty steps and we need to generate different configuration of these
# - we simulate it being stuck in MONITOR, STOP, START
# - try to emulate all possible combinations so that we can see if there are any errors


# TODO: try to recover form error states as well
# mock with event wait and set & wait forever if enabled


# TODO: cancelling this is hard, should work faster, why not have a step that waits instead of the _core?
