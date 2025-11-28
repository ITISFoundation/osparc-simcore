# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Final
from unittest.mock import Mock, call
from uuid import uuid4

import pytest
from fastapi import FastAPI
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_scheduler.services.generic_scheduler import (
    OperationToStart,
    enqueue_execute_completed_event,
    enqueue_revert_completed_event,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._event import (
    enqueue_schedule_event,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
    EventType,
    ScheduleId,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


_RETRY_PARAMS: Final[dict[str, Any]] = {
    "wait": wait_fixed(0.1),
    "stop": stop_after_delay(5),
    "retry": retry_if_exception_type(AssertionError),
}


@pytest.fixture
def disable_other_generic_scheduler_modules(mocker: MockerFixture) -> None:
    # these also use redis
    generic_scheduler_module = (
        "simcore_service_dynamic_scheduler.services.generic_scheduler"
    )
    mocker.patch(f"{generic_scheduler_module}._lifespan.Core", autospec=True)
    mocker.patch(f"{generic_scheduler_module}._lifespan.Store", autospec=True)
    mocker.patch(
        f"{generic_scheduler_module}._lifespan.AfterEventManager", autospec=True
    )


@pytest.fixture
def app_environment(
    disable_scheduler_lifespan: None,
    disable_other_generic_scheduler_modules: None,
    disable_redis_lifespan: None,
    disable_postgres_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    app_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def get_mock_safe_on_schedule_event(
    mocker: MockerFixture,
) -> Callable[[Callable[[ScheduleId], Awaitable[None]]], Mock]:

    def _(side_effect: Callable[[ScheduleId], Awaitable[None]]) -> Mock:
        another_mock = Mock()

        async def _mock(schedule_id: ScheduleId) -> None:
            await side_effect(schedule_id)
            another_mock(schedule_id)

        core_mock = Mock()
        core_mock.safe_on_schedule_event = _mock
        mocker.patch(
            "simcore_service_dynamic_scheduler.services.generic_scheduler._event_queues.get_core",
            return_value=core_mock,
        )
        return another_mock

    return _


async def test_enqueue_schedule_event(
    get_mock_safe_on_schedule_event: Callable[
        [Callable[[ScheduleId], Awaitable[None]]], Mock
    ],
    app: FastAPI,
) -> None:

    async def _side_effect_nothing(schedule_id: ScheduleId) -> None:
        pass

    mock = get_mock_safe_on_schedule_event(_side_effect_nothing)

    schedule_id = TypeAdapter(ScheduleId).validate_python(f"{uuid4()}")
    await enqueue_schedule_event(app, schedule_id)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            await asyncio.sleep(0)  # wait for event to trigger
            assert mock.call_args_list == [call(schedule_id)]


async def test_enqueue_schedule_event_raises_error(
    get_mock_safe_on_schedule_event: Callable[
        [Callable[[ScheduleId], Awaitable[None]]], Mock
    ],
    app: FastAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.clear()

    async def _side_effect_raise_error(schedule_id: ScheduleId) -> None:
        msg = "always failing here as requested"
        raise RuntimeError(msg)

    get_mock_safe_on_schedule_event(_side_effect_raise_error)

    schedule_id = TypeAdapter(ScheduleId).validate_python(f"{uuid4()}")
    await enqueue_schedule_event(app, schedule_id)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            await asyncio.sleep(0)  # wait for event to trigger
            assert "Unexpected error. Aborting message retry" in caplog.text


@pytest.fixture
def get_mock_safe_on_event_type(
    mocker: MockerFixture,
) -> Callable[
    [Callable[[EventType, ScheduleId, OperationToStart], Awaitable[None]]], Mock
]:

    def _(
        side_effect: Callable[
            [EventType, ScheduleId, OperationToStart], Awaitable[None]
        ],
    ) -> Mock:
        another_mock = Mock()

        async def _mock(
            event_type: EventType,
            schedule_id: ScheduleId,
            to_start: OperationToStart,
            *,
            on_execute_completed: OperationToStart | None = None,
            on_revert_completed: OperationToStart | None = None,
        ) -> None:
            await side_effect(event_type, schedule_id, to_start)
            another_mock(event_type, schedule_id, to_start)

        core_mock = Mock()
        core_mock.safe_on_event_type = _mock
        mocker.patch(
            "simcore_service_dynamic_scheduler.services.generic_scheduler._event_queues.get_after_event_manager",
            return_value=core_mock,
        )
        return another_mock

    return _


@pytest.mark.parametrize("expected_event_type", EventType)
async def test_enqueue_event_type(
    get_mock_safe_on_event_type: Callable[
        [Callable[[EventType, ScheduleId, OperationToStart], Awaitable[None]]], Mock
    ],
    app: FastAPI,
    expected_event_type: EventType,
):

    async def _side_effect_nothing(
        event_type: EventType,
        schedule_id: ScheduleId,
        to_start: OperationToStart,
        *,
        on_execute_completed: OperationToStart | None = None,
        on_revert_completed: OperationToStart | None = None,
    ) -> None:
        pass

    mock = get_mock_safe_on_event_type(_side_effect_nothing)

    schedule_id = TypeAdapter(ScheduleId).validate_python(f"{uuid4()}")
    match expected_event_type:
        case EventType.ON_EXECUTEDD_COMPLETED:
            await enqueue_execute_completed_event(
                app, schedule_id, OperationToStart("op1", {})
            )
        case EventType.ON_REVERT_COMPLETED:
            await enqueue_revert_completed_event(
                app, schedule_id, OperationToStart("op1", {})
            )
        case _:
            pytest.fail("unsupported case")

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)  # wait for event to trigger
            assert mock.call_args_list == [
                call(expected_event_type, schedule_id, OperationToStart("op1", {}))
            ]


@pytest.mark.parametrize("expected_event_type", EventType)
async def test_enqueue_event_type_raises_error(
    get_mock_safe_on_event_type: Callable[
        [Callable[[EventType, ScheduleId, OperationToStart], Awaitable[None]]], Mock
    ],
    app: FastAPI,
    caplog: pytest.LogCaptureFixture,
    expected_event_type: EventType,
) -> None:
    caplog.clear()

    async def _side_effect_raise_error(
        event_type: EventType,
        schedule_id: ScheduleId,
        to_start: OperationToStart,
    ) -> None:
        msg = "always failing here as requested"
        raise RuntimeError(msg)

    get_mock_safe_on_event_type(_side_effect_raise_error)

    schedule_id = TypeAdapter(ScheduleId).validate_python(f"{uuid4()}")

    match expected_event_type:
        case EventType.ON_EXECUTEDD_COMPLETED:
            await enqueue_execute_completed_event(
                app, schedule_id, OperationToStart("op1", {})
            )
        case EventType.ON_REVERT_COMPLETED:
            await enqueue_revert_completed_event(
                app, schedule_id, OperationToStart("op1", {})
            )
        case _:
            pytest.fail("unsupported case")

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)  # wait for event to trigger
            assert "Unexpected error. Aborting message retry" in caplog.text
