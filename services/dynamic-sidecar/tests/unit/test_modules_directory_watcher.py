# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
from pathlib import Path
from shutil import move
from typing import Iterator
from unittest.mock import AsyncMock

import pytest
from pytest import MonkeyPatch
from simcore_service_dynamic_sidecar.modules.directory_watcher import (
    _core as directory_watcher_core,
)
from simcore_service_dynamic_sidecar.modules.directory_watcher._core import (
    DirectoryWatcherObservers,
)

TICK_INTERVAL = 0.001


@pytest.fixture
def patch_directory_watcher(monkeypatch: MonkeyPatch) -> Iterator[AsyncMock]:
    mocked_upload_data = AsyncMock(return_value=None)

    monkeypatch.setattr(directory_watcher_core, "DETECTION_INTERVAL", TICK_INTERVAL)
    monkeypatch.setattr(directory_watcher_core, "_push_directory", mocked_upload_data)

    yield mocked_upload_data


# UTILS


async def _generate_event_burst(tmp_path: Path, subfolder: str = None) -> None:
    full_dir_path = tmp_path if subfolder is None else tmp_path / subfolder
    full_dir_path.mkdir(parents=True, exist_ok=True)
    file_path_1 = full_dir_path / "file1.txt"
    file_path_2 = full_dir_path / "file2.txt"
    # create
    file_path_1.touch()
    # modified
    file_path_1.write_text("lorem ipsum")
    # move
    move(str(file_path_1), str(file_path_2))
    # delete
    file_path_2.unlink()
    # let fs events trigger
    await asyncio.sleep(TICK_INTERVAL)


async def _wait_for_events_to_trigger() -> None:
    await asyncio.sleep(3)


async def test_run_observer(
    patch_directory_watcher: AsyncMock,
    tmp_path: Path,
) -> None:

    directory_watcher_observers = DirectoryWatcherObservers(io_log_redirect_cb=None)
    directory_watcher_observers.observe_directory(tmp_path)

    directory_watcher_observers.start()
    directory_watcher_observers.start()

    await asyncio.sleep(TICK_INTERVAL)

    # generates the first event chain
    await _generate_event_burst(tmp_path)

    await _wait_for_events_to_trigger()

    # generates the second event chain
    await _generate_event_burst(tmp_path, "ciao")

    await directory_watcher_observers.stop()
    await directory_watcher_observers.stop()

    # pylint: disable=protected-access
    assert directory_watcher_observers._keep_running is False
    assert directory_watcher_observers._blocking_task is None

    assert patch_directory_watcher.call_count == 2


async def test_does_not_trigger_on_attribute_change(
    patch_directory_watcher: AsyncMock, tmp_path: Path
):
    directory_watcher_observers = DirectoryWatcherObservers(io_log_redirect_cb=None)
    directory_watcher_observers.observe_directory(tmp_path)

    directory_watcher_observers.start()

    await asyncio.sleep(TICK_INTERVAL)

    # crate a file in the directory
    tmp_path.mkdir(parents=True, exist_ok=True)
    file_path_1 = tmp_path / "file1.txt"
    file_path_1.touch()

    await _wait_for_events_to_trigger()
    assert patch_directory_watcher.call_count == 1

    # apply an attribute change
    file_path_1.chmod(0o744)

    await _wait_for_events_to_trigger()
    # same call count as before, event was ignored
    assert patch_directory_watcher.call_count == 1
