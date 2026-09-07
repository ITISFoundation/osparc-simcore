# pylint: disable=redefined-outer-name
# pylint: disable=protected-access

import asyncio
import multiprocessing
from collections.abc import AsyncIterable
from multiprocessing.queues import Queue
from pathlib import Path
from threading import Event, Thread
from typing import Any, Final
from unittest.mock import Mock

import pytest
from pydantic import PositiveFloat
from pytest_mock import MockerFixture
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
async def outputs_context(path_to_observe: Path, outputs_port_keys: list[str]) -> OutputsContext:
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
def health_check_queue() -> Queue[int | None]:
    return multiprocessing.Queue()


@pytest.fixture
def heart_beat_interval_s() -> PositiveFloat:
    return 0.01


async def test_event_handler_process_lifecycle(
    outputs_context: OutputsContext,
    health_check_queue: Queue[int | None],
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


def test_event_handler_process_concurrent_stop_process_does_not_raise(
    outputs_context: OutputsContext,
    health_check_queue: Queue[int | None],
    heart_beat_interval_s: PositiveFloat,
):
    observer_process = _EventHandlerProcess(
        outputs_context=outputs_context,
        health_check_queue=health_check_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    entered_kill = Event()
    release_kill = Event()
    first_caller_paused = False

    def _kill() -> None:
        nonlocal first_caller_paused
        # only the first caller pauses: it must observe `self._process` as
        # non-`None` for longer than it takes a concurrent caller to clear it
        if not first_caller_paused:
            first_caller_paused = True
            entered_kill.set()
            assert release_kill.wait(timeout=5), "test setup: never released"

    mock_process = Mock()
    mock_process.kill.side_effect = _kill
    observer_process._process = mock_process  # noqa: SLF001

    errors: list[BaseException] = []

    def _stop_process() -> None:
        try:
            observer_process.stop_process()
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    first_thread = Thread(target=_stop_process)
    first_thread.start()
    assert entered_kill.wait(timeout=5), "first thread never reached kill()"

    # with the lock this blocks on `_process_lock` and cannot make progress
    # while the first thread is paused mid-`kill()`; without it, it runs to
    # completion (clearing `self._process`) before the first thread resumes
    second_thread = Thread(target=_stop_process)
    second_thread.start()
    second_thread.join(timeout=0.5)
    assert second_thread.is_alive(), "stop_process proceeded before first stop_process released the lock"

    release_kill.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive(), "first thread never completed (deadlock?)"
    assert not second_thread.is_alive(), "second thread never completed (deadlock?)"
    assert not errors


def test_event_handler_process_concurrent_start_vs_stop_process_does_not_raise(
    outputs_context: OutputsContext,
    health_check_queue: Queue[int | None],
    heart_beat_interval_s: PositiveFloat,
    mocker: MockerFixture,
):
    observer_process = _EventHandlerProcess(
        outputs_context=outputs_context,
        health_check_queue=health_check_queue,
        heart_beat_interval_s=heart_beat_interval_s,
    )

    entered_start = Event()
    release_start = Event()
    first_caller_paused = False

    def _start() -> None:
        nonlocal first_caller_paused
        # pauses while `start_process` still holds `_process_lock`
        if not first_caller_paused:
            first_caller_paused = True
            entered_start.set()
            assert release_start.wait(timeout=5), "test setup: never released"

    mock_process_cls = Mock()
    mock_process_cls.return_value.start.side_effect = _start
    mocker.patch.object(multiprocessing, "Process", mock_process_cls)

    errors: list[BaseException] = []

    def _start_process() -> None:
        try:
            observer_process.start_process()
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    def _stop_process() -> None:
        try:
            observer_process.stop_process()
        except BaseException as exc:  # pylint: disable=broad-except
            errors.append(exc)

    start_thread = Thread(target=_start_process)
    start_thread.start()
    assert entered_start.wait(timeout=5), "start thread never reached start()"

    # must block on `_process_lock` while `start_process` is still in progress
    stop_thread = Thread(target=_stop_process)
    stop_thread.start()
    stop_thread.join(timeout=0.5)
    assert stop_thread.is_alive(), "stop_process proceeded before start_process released the lock"

    release_start.set()
    start_thread.join(timeout=5)
    stop_thread.join(timeout=5)

    assert not start_thread.is_alive(), "start thread never completed (deadlock?)"
    assert not stop_thread.is_alive(), "stop thread never completed (deadlock?)"
    assert not errors


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


class _MockQueue:
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
            FileClosedEvent(src_path=f"{_STATE_PATH}/output_1/asdsadsasad.txt", dest_path=""),
            "output_1",
            id="close_file_inside_triggers_event",
        ),
    ],
)
def test_port_keys_event_handler_triggers_for_events(
    mock_state_path: Path, event: FileSystemEvent, expected_port_key: str | None
) -> None:
    queue = _MockQueue()

    event_handler = _PortKeysEventHandler(mock_state_path, queue)
    event_handler.handle_set_outputs_port_keys(outputs_port_keys={"output_1"})
    event_handler.handle_toggle_event_propagation(is_enabled=True)

    event_handler.event_handler(event)
    assert queue.get() == expected_port_key
