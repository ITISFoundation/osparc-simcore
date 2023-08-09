# pylint: disable=redefined-outer-name

import asyncio
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from simcore_service_dynamic_sidecar.modules.outputs._watchdog_extensions import (
    ExtendedInotifyObserver,
    SafeFileSystemEventHandler,
)
from watchdog.events import FileSystemEvent, FileSystemEventHandler


@pytest.fixture
def path_to_observe(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def mocked_file_system_event() -> FileSystemEvent:
    return FileSystemEvent("/fake/path/for/event")


async def _generate_events(dir_path: Path, event_count: int = 10) -> None:
    for _ in range(event_count):
        file_path_1 = dir_path / f"file{uuid4()}.txt"
        file_path_1.touch()


@pytest.mark.parametrize("fail_once", [True, False])
async def test_regression_watchdog_blocks_on_handler_error(
    path_to_observe: Path, fail_once: bool
):
    raised_error = False
    event_handler = Mock()

    class MockedEventHandler(FileSystemEventHandler):
        def on_any_event(self, event: FileSystemEvent) -> None:
            super().on_any_event(event)
            event_handler()
            nonlocal raised_error
            if not raised_error and fail_once:
                raised_error = True
                raise RuntimeError("raised as expected")

    observer = ExtendedInotifyObserver()
    observer.schedule(
        event_handler=MockedEventHandler(),
        path=f"{path_to_observe}",
        recursive=True,
    )
    observer.start()

    await _generate_events(path_to_observe)

    WAIT_FOR_EVENT_PROPAGATION = 0.1
    await asyncio.sleep(WAIT_FOR_EVENT_PROPAGATION)

    if fail_once:
        # if an error is raised by `on_any_event`
        # watchdog will stop handling events
        assert event_handler.call_count == 1
    else:
        # if no errors are raised no the process will
        # continue
        assert event_handler.call_count > 1


@pytest.mark.parametrize("user_code_raises_error", [True, False])
async def test_safe_file_system_event_handler(
    mocked_file_system_event: FileSystemEvent, user_code_raises_error: bool
):
    class MockedEventHandler(SafeFileSystemEventHandler):
        def event_handler(self, _: FileSystemEvent) -> None:
            if user_code_raises_error:
                raise RuntimeError("error was raised")

    mocked_handler = MockedEventHandler()
    mocked_handler.on_any_event(mocked_file_system_event)
