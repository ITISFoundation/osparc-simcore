# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
from pathlib import Path
from typing import AsyncIterator, Iterator
from unittest.mock import AsyncMock

import pytest
from pydantic import NonNegativeFloat, NonNegativeInt
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar.modules.directory_watcher._event_filter import (
    BaseWaitPolicy,
    EventFilter,
    DefaultWaitPolicy,
)
from simcore_service_dynamic_sidecar.modules.outputs_manager import OutputsManager
from watchdog.events import FileModifiedEvent, FileSystemEvent

# FIXTURES


@pytest.fixture
def outputs_path(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def port_key_1() -> str:
    return "port_1"


@pytest.fixture
def file_system_event(outputs_path: Path, port_key_1: str) -> FileSystemEvent:
    file_path = outputs_path / port_key_1 / "file"
    return FileModifiedEvent(src_path=f"{file_path}")


@pytest.fixture
def port_keys(outputs_path: Path, port_key_1: str) -> list[str]:
    (outputs_path / port_key_1).mkdir(parents=True, exist_ok=True)
    return [port_key_1]


@pytest.fixture
async def outputs_manager(
    outputs_path: Path, port_keys: list[str]
) -> AsyncIterator[OutputsManager]:
    outputs_manager = OutputsManager(outputs_path=outputs_path, port_keys=port_keys)
    yield outputs_manager
    await outputs_manager.shutdown()


@pytest.fixture
def mocked_upload_after_port_change(
    mocker: MockerFixture, outputs_manager: OutputsManager
) -> Iterator[AsyncMock]:
    async def _mock_upload_outputs(*args, **kwargs) -> None:
        pass

    yield mocker.patch.object(
        outputs_manager, "upload_after_port_change", side_effect=_mock_upload_outputs
    )


@pytest.fixture
def mock_wait_policy() -> BaseWaitPolicy:
    VERY_FAST_BASE = 0.001
    SLOW_LONG_INTERVAL = VERY_FAST_BASE * 100

    # pylint:disable=no-self-use
    class FastPolicy(BaseWaitPolicy):
        def get_base(self) -> NonNegativeFloat:
            return VERY_FAST_BASE

        def get_wait_interval(self, dir_size: NonNegativeInt) -> NonNegativeFloat:
            return VERY_FAST_BASE if dir_size == 0 else SLOW_LONG_INTERVAL

    return FastPolicy()


@pytest.fixture
def mock_get_dir_size(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.directory_watcher._event_filter.get_dir_size",
        return_value=1,
    )


@pytest.fixture
async def event_filter(
    outputs_manager: OutputsManager, mock_wait_policy: BaseWaitPolicy
) -> AsyncIterator[EventFilter]:
    event_filter = EventFilter(
        outputs_manager=outputs_manager,
        wait_policy=mock_wait_policy,
        io_log_redirect_cb=None,
    )
    await event_filter.start()
    yield event_filter
    await event_filter.shutdown()


# UTILS


async def _wait_for_event_to_trigger(event_filter: EventFilter) -> None:
    await asyncio.sleep(event_filter.wait_policy.get_base() * 2)


async def _wait_for_event_to_trigger_big_directory(event_filter: EventFilter) -> None:
    await asyncio.sleep(event_filter.wait_policy.get_wait_interval(1) * 2)


# TESTS


async def test_event_triggers_once(
    event_filter: EventFilter,
    port_key_1: str,
    file_system_event: FileSystemEvent,
    mocked_upload_after_port_change: AsyncMock,
):
    # event triggers once
    event_filter.enqueue(port_key_1, file_system_event)
    await _wait_for_event_to_trigger(event_filter)
    assert mocked_upload_after_port_change.call_count == 1

    await _wait_for_event_to_trigger(event_filter)

    # event triggers a second time
    event_filter.enqueue(port_key_1, file_system_event)
    await _wait_for_event_to_trigger(event_filter)
    assert mocked_upload_after_port_change.call_count == 2


async def test_trigger_once_after_event_chain(
    event_filter: EventFilter,
    port_key_1: str,
    file_system_event: FileSystemEvent,
    mocked_upload_after_port_change: AsyncMock,
):
    for _ in range(100):
        event_filter.enqueue(port_key_1, file_system_event)
    await _wait_for_event_to_trigger(event_filter)
    assert mocked_upload_after_port_change.call_count == 1


async def test_always_trigger_after_delay(
    mock_get_dir_size: None,
    event_filter: EventFilter,
    port_key_1: str,
    file_system_event: FileSystemEvent,
    mocked_upload_after_port_change: AsyncMock,
):
    # event triggers once
    event_filter.enqueue(port_key_1, file_system_event)
    await _wait_for_event_to_trigger(event_filter)
    assert mocked_upload_after_port_change.call_count == 0

    # ensure event is drained
    await _wait_for_event_to_trigger_big_directory(event_filter)
    assert mocked_upload_after_port_change.call_count == 1

    # trigger once more and see if it triggers after expected interval
    event_filter.enqueue(port_key_1, file_system_event)
    await _wait_for_event_to_trigger_big_directory(event_filter)
    assert mocked_upload_after_port_change.call_count == 2


def test_default_wait_policy():
    wait_policy = DefaultWaitPolicy()

    KB = 1024
    MB = 1024 * KB
    GB = 1024 * MB
    LOWER_BOUND = 1 * MB  # coming from the default policy
    UPPER_BOUND = 500 * MB  # coming from the default policy

    assert wait_policy.get_base() == 1.0

    assert wait_policy.get_wait_interval(-1) == 1.0
    assert wait_policy.get_wait_interval(LOWER_BOUND - 1) == 1.0
    assert wait_policy.get_wait_interval(LOWER_BOUND) == 1.0
    assert wait_policy.get_wait_interval(LOWER_BOUND + 1) > 1.0

    assert wait_policy.get_wait_interval(UPPER_BOUND - 1) < 10.0
    assert wait_policy.get_wait_interval(UPPER_BOUND) == 10.0
    assert wait_policy.get_wait_interval(UPPER_BOUND + 1) == 10.0
    assert wait_policy.get_wait_interval(1024 * GB) == 10.0
