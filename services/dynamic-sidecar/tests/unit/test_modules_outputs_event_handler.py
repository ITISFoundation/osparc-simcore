# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import asyncio
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any, Final
from unittest.mock import Mock

import aioprocessing
import pytest
from aioprocessing.queues import AioQueue
from pydantic import PositiveFloat
from simcore_service_dynamic_sidecar.modules.notifications._notifications_ports import (
    PortNotifier,
)
from simcore_service_dynamic_sidecar.modules.outputs._context import OutputsContext
from simcore_service_dynamic_sidecar.modules.outputs._event_handler import (
    EventHandlerObserver,
    _EventHandlerProcess,
    _PortKeysEventHandler,
)
from simcore_service_dynamic_sidecar.modules.outputs._manager import OutputsManager
from watchdog.events import (
    DirModifiedEvent,
    FileClosedEvent,
    FileCreatedEvent,
    FileMovedEvent,
    FileSystemEvent,
)


@pytest.fixture
def path_to_observe(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def outputs_port_keys() -> list[str]:
    return [f"port_key_{i}" for i in range(1, 10)]


@pytest.fixture
async def outputs_context(
    path_to_observe: Path, outputs_port_keys: list[str]
) -> OutputsContext:
    outputs_context = OutputsContext(path_to_observe)
    await outputs_context.set_file_type_port_keys(outputs_port_keys)
    return outputs_context


@pytest.fixture
async def outputs_manager(
    outputs_context: OutputsContext, port_notifier: PortNotifier
) -> AsyncIterable[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_context,
        port_notifier=port_notifier,
        io_log_redirect_cb=None,
        progress_cb=None,
    )
    await outputs_manager.start()

    outputs_manager.set_all_ports_for_upload = Mock()

    yield outputs_manager
    await outputs_manager.shutdown()


@pytest.fixture
def health_check_queue() -> AioQueue:
    return aioprocessing.AioQueue()


@pytest.fixture
def heart_beat_interval_s() -> PositiveFloat:
    return 0.01


async def test_event_handler_process_lifecycle(
    outputs_context: OutputsContext,
    health_check_queue: AioQueue,
    heart_beat_interval_s: PositiveFloat,
):
    observer_process = _EventHandlerProcess(
        outputs_context=outputs_context,
        health_check_queue=health_check_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    observer_process.start_process()
    await asyncio.sleep(heart_beat_interval_s * 10)
    observer_process.stop_process()

    observer_process.shutdown()


async def test_event_handler_observer_health_ok(
    outputs_context: OutputsContext,
    outputs_manager: OutputsManager,
    heart_beat_interval_s: PositiveFloat,
):
    observer_monitor = EventHandlerObserver(
        outputs_context=outputs_context,
        outputs_manager=outputs_manager,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    await observer_monitor.start()
    await asyncio.sleep(heart_beat_interval_s * 10)

    await asyncio.sleep(observer_monitor.wait_for_heart_beat_interval_s * 10)
    await observer_monitor.stop()
    assert outputs_manager.set_all_ports_for_upload.call_count == 0


async def test_event_handler_observer_health_degraded(
    outputs_context: OutputsContext,
    outputs_manager: OutputsManager,
    heart_beat_interval_s: PositiveFloat,
):
    observer_monitor = EventHandlerObserver(
        outputs_context=outputs_context,
        outputs_manager=outputs_manager,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    await observer_monitor.start()

    # emulate observer stuck
    observer_monitor._event_handler_process.stop_process()

    await asyncio.sleep(observer_monitor.wait_for_heart_beat_interval_s * 3)
    await observer_monitor.stop()
    assert outputs_manager.set_all_ports_for_upload.call_count >= 1


_STATE_PATH: Final[Path] = Path("/some/random/fake/path/for/state/")


@pytest.fixture
def mock_state_path() -> Path:
    return _STATE_PATH


class _MockAioQueue:
    def __init__(self) -> None:
        self.items: list[Any] = []

    def put(self, item: Any) -> None:
        self.items.append(item)

    def get(self) -> Any | None:
        try:
            return self.items.pop()
        except IndexError:
            return None


@pytest.mark.parametrize(
    "event, expected_port_key",
    [
        pytest.param(
            FileCreatedEvent(src_path=f"{_STATE_PATH}/untitled.txt", dest_path=""),
            None,
            id="file_create_outside",
        ),
        pytest.param(
            FileCreatedEvent(
                src_path=f"{_STATE_PATH}/output_1/untitled1.txt",
                dest_path="",
            ),
            "output_1",
            id="file_create_inside_monitored_port",
        ),
        pytest.param(
            FileCreatedEvent(
                src_path=f"{_STATE_PATH}/output_9/untitled1.txt",
                dest_path="",
            ),
            None,
            id="file_create_inside_not_monitored_port",
        ),
        pytest.param(
            FileMovedEvent(
                src_path=f"{_STATE_PATH}/untitled.txt",
                dest_path=f"{_STATE_PATH}/asdsadsasad.txt",
            ),
            None,
            id="move_outside_any_port",
        ),
        pytest.param(
            FileMovedEvent(
                src_path=f"{_STATE_PATH}/asdsadsasad.txt",
                dest_path=f"{_STATE_PATH}/output_1/asdsadsasad.txt",
            ),
            "output_1",
            id="move_to_monitored_port",
        ),
        pytest.param(
            FileMovedEvent(
                src_path=f"{_STATE_PATH}/asdsadsasad.txt",
                dest_path=f"{_STATE_PATH}/output_9/asdsadsasad.txt",
            ),
            None,
            id="move_outside_monitored_port",
        ),
        pytest.param(
            DirModifiedEvent(src_path=f"{_STATE_PATH}/output_1", dest_path=""),
            None,
            id="modified_port_dir_does_nothing",
        ),
        pytest.param(
            DirModifiedEvent(src_path=f"{_STATE_PATH}", dest_path=""),
            None,
            id="modified_outer_dir_does_nothing",
        ),
        pytest.param(
            FileClosedEvent(src_path=f"{_STATE_PATH}/untitled.txt", dest_path=""),
            None,
            id="close_file_outside_does_nothing",
        ),
        pytest.param(
            FileClosedEvent(
                src_path=f"{_STATE_PATH}/output_1/asdsadsasad.txt", dest_path=""
            ),
            "output_1",
            id="close_file_inside_triggers_event",
        ),
    ],
)
def test_port_keys_event_handler_triggers_for_events(
    mock_state_path: Path, event: FileSystemEvent, expected_port_key: str | None
) -> None:

    queue = _MockAioQueue()

    event_handler = _PortKeysEventHandler(mock_state_path, queue)
    event_handler.handle_set_outputs_port_keys(outputs_port_keys={"output_1"})
    event_handler.handle_toggle_event_propagation(is_enabled=True)

    event_handler.event_handler(event)
    assert queue.get() == expected_port_key
