# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from pydantic import ByteSize, NonNegativeFloat, NonNegativeInt, TypeAdapter
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.modules.notifications._notifications_ports import (
    PortNotifier,
)
from simcore_service_dynamic_sidecar.modules.outputs._context import OutputsContext
from simcore_service_dynamic_sidecar.modules.outputs._event_filter import (
    BaseDelayPolicy,
    DefaultDelayPolicy,
    EventFilter,
)
from simcore_service_dynamic_sidecar.modules.outputs._manager import OutputsManager
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

_TENACITY_RETRY_PARAMS = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "stop": stop_after_delay(10),
    "wait": wait_fixed(0.01),
}

# FIXTURES


@pytest.fixture
def outputs_path(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def port_key_1() -> str:
    return "port_1"


@pytest.fixture
def port_keys(outputs_path: Path, port_key_1: str) -> list[str]:
    (outputs_path / port_key_1).mkdir(parents=True, exist_ok=True)
    return [port_key_1]


@pytest.fixture
async def outputs_context(outputs_path: Path, port_keys: list[str]) -> OutputsContext:
    outputs_context = OutputsContext(outputs_path)
    await outputs_context.set_file_type_port_keys(port_keys)
    return outputs_context


@pytest.fixture
async def outputs_manager(
    outputs_context: OutputsContext, port_notifier: PortNotifier
) -> AsyncIterator[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_context=outputs_context,
        port_notifier=port_notifier,
        io_log_redirect_cb=None,
        progress_cb=None,
    )
    await outputs_manager.start()
    yield outputs_manager
    await outputs_manager.shutdown()


@pytest.fixture
def mocked_port_key_content_changed(
    mocker: MockerFixture, outputs_manager: OutputsManager
) -> AsyncMock:
    async def _mock_upload_outputs(*args, **kwargs) -> None:
        pass

    return mocker.patch.object(
        outputs_manager, "port_key_content_changed", side_effect=_mock_upload_outputs
    )


@pytest.fixture
def mock_delay_policy() -> BaseDelayPolicy:
    VERY_FAST_BASE = 0.001
    SLOW_LONG_INTERVAL = VERY_FAST_BASE * 100

    # pylint:disable=no-self-use
    class FastPolicy(BaseDelayPolicy):
        def get_min_interval(self) -> NonNegativeFloat:
            return VERY_FAST_BASE

        def get_wait_interval(self, dir_size: NonNegativeInt) -> NonNegativeFloat:
            return VERY_FAST_BASE if dir_size == 0 else SLOW_LONG_INTERVAL

    return FastPolicy()


@pytest.fixture
def mock_get_directory_total_size(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._event_filter.get_directory_total_size",
        return_value=1,
    )


@pytest.fixture
async def event_filter(
    outputs_manager: OutputsManager, mock_delay_policy: BaseDelayPolicy
) -> AsyncIterator[EventFilter]:
    event_filter = EventFilter(
        outputs_manager=outputs_manager, delay_policy=mock_delay_policy
    )
    await event_filter.start()
    yield event_filter
    await event_filter.shutdown()


# UTILS


async def _wait_for_event_to_trigger(event_filter: EventFilter) -> None:
    await asyncio.sleep(event_filter.delay_policy.get_min_interval() * 5)


# TESTS


async def test_event_triggers_once(
    event_filter: EventFilter,
    port_key_1: str,
    mocked_port_key_content_changed: AsyncMock,
):
    # event triggers once
    await event_filter.enqueue(port_key_1)
    await _wait_for_event_to_trigger(event_filter)
    assert mocked_port_key_content_changed.call_count == 1

    # event triggers a second time
    await event_filter.enqueue(port_key_1)
    await _wait_for_event_to_trigger(event_filter)
    assert mocked_port_key_content_changed.call_count == 2


async def test_trigger_once_after_event_chain(
    event_filter: EventFilter,
    port_key_1: str,
    mocked_port_key_content_changed: AsyncMock,
):
    for _ in range(100):
        await event_filter.enqueue(port_key_1)
    await _wait_for_event_to_trigger(event_filter)
    assert mocked_port_key_content_changed.call_count == 1


async def test_always_trigger_after_delay(
    mock_get_directory_total_size: AsyncMock,
    event_filter: EventFilter,
    port_key_1: str,
    mocked_port_key_content_changed: AsyncMock,
):
    # event trigger after correct interval delay correctly
    for expected_call_count in range(1, 10):
        await event_filter.enqueue(port_key_1)
        async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
            with attempt:
                assert mocked_port_key_content_changed.call_count == expected_call_count


async def test_minimum_amount_of_get_directory_total_size_calls(
    mock_get_directory_total_size: AsyncMock,
    event_filter: EventFilter,
    port_key_1: str,
    mocked_port_key_content_changed: AsyncMock,
):
    await event_filter.enqueue(port_key_1)
    # wait a bit for the vent to be picked up
    # by the workers and processed
    await _wait_for_event_to_trigger(event_filter)
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            assert mock_get_directory_total_size.call_count == 1
            assert mocked_port_key_content_changed.call_count == 0

    # event finished processing and was dispatched
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            assert mock_get_directory_total_size.call_count == 2
            assert mocked_port_key_content_changed.call_count == 1


async def test_minimum_amount_of_get_directory_total_size_calls_with_continuous_changes(
    mock_get_directory_total_size: AsyncMock,
    event_filter: EventFilter,
    port_key_1: str,
    mocked_port_key_content_changed: AsyncMock,
):
    await event_filter.enqueue(port_key_1)
    # wait a bit for the vent to be picked up
    # by the workers and processed
    await _wait_for_event_to_trigger(event_filter)
    assert mock_get_directory_total_size.call_count == 1
    assert mocked_port_key_content_changed.call_count == 0

    # while changes keep piling up, keep extending the duration
    # no event will trigger
    # size of directory will not be computed
    VERY_LONG_EVENT_CHAIN = 1000
    for _ in range(VERY_LONG_EVENT_CHAIN):
        await event_filter.enqueue(port_key_1)
        await _wait_for_event_to_trigger(event_filter)
        assert mock_get_directory_total_size.call_count == 1
        assert mocked_port_key_content_changed.call_count == 0

    # event finished processing and was dispatched
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            assert mock_get_directory_total_size.call_count == 2
            assert mocked_port_key_content_changed.call_count == 1


def test_default_delay_policy():
    wait_policy = DefaultDelayPolicy()

    # below items are defined by the default policy
    LOWER_BOUND = TypeAdapter(ByteSize).validate_python("1mib")
    UPPER_BOUND = TypeAdapter(ByteSize).validate_python("500mib")

    assert wait_policy.get_min_interval() == 1.0

    assert wait_policy.get_wait_interval(-1) == 1.0
    assert wait_policy.get_wait_interval(LOWER_BOUND - 1) == 1.0
    assert wait_policy.get_wait_interval(LOWER_BOUND) == 1.0
    assert wait_policy.get_wait_interval(LOWER_BOUND + 1) > 1.0

    assert wait_policy.get_wait_interval(UPPER_BOUND - 1) < 10.0
    assert wait_policy.get_wait_interval(UPPER_BOUND) == 10.0
    assert wait_policy.get_wait_interval(UPPER_BOUND + 1) == 10.0
    assert (
        wait_policy.get_wait_interval(TypeAdapter(ByteSize).validate_python("1Tib"))
        == 10.0
    )
