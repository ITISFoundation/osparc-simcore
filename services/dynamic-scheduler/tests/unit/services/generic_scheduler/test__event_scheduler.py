# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import Mock, call
from uuid import uuid4

import pytest
from fastapi import FastAPI
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_scheduler.services.generic_scheduler._event_scheduler import (
    EventScheduler,
)
from simcore_service_dynamic_scheduler.services.generic_scheduler._models import (
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


@pytest.fixture
def disable_other_generic_scheduler_modules(mocker: MockerFixture) -> None:
    # these also use redis
    generic_scheduler_module = (
        "simcore_service_dynamic_scheduler.services.generic_scheduler"
    )
    mocker.patch(f"{generic_scheduler_module}._lifespan.Core", autospec=True)
    mocker.patch(f"{generic_scheduler_module}._lifespan.Store", autospec=True)


@pytest.fixture
def app_environment(
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
def event_scheduler(app: FastAPI) -> EventScheduler:
    return app.state.generic_scheduler_event_scheduler


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
            "simcore_service_dynamic_scheduler.services.generic_scheduler._event_scheduler.Core.get_from_app_state",
            return_value=core_mock,
        )
        return another_mock

    return _


async def _side_effect_nothing(schedule_id: ScheduleId) -> None:
    pass


async def _side_effect_raise_error(schedule_id: ScheduleId) -> None:
    msg = "always failing here as requesed"
    raise RuntimeError(msg)


async def test_event_scheduling(
    get_mock_safe_on_schedule_event: Callable[
        [Callable[[ScheduleId], Awaitable[None]]], Mock
    ],
    event_scheduler: EventScheduler,
) -> None:
    mock = get_mock_safe_on_schedule_event(_side_effect_nothing)

    schedule_id = TypeAdapter(ScheduleId).validate_python(f"{uuid4()}")
    await event_scheduler.enqueue_schedule_event(schedule_id)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            await asyncio.sleep(0)  # wait for envet to trigger
            assert mock.call_args_list == [call(schedule_id)]


async def test_event_scheduling_raises_error(
    get_mock_safe_on_schedule_event: Callable[
        [Callable[[ScheduleId], Awaitable[None]]], Mock
    ],
    event_scheduler: EventScheduler,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.clear()
    get_mock_safe_on_schedule_event(_side_effect_raise_error)

    schedule_id = TypeAdapter(ScheduleId).validate_python(f"{uuid4()}")
    await event_scheduler.enqueue_schedule_event(schedule_id)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            await asyncio.sleep(0)  # wait for envet to trigger
            assert "Unexpected error. Aborting message retry" in caplog.text
