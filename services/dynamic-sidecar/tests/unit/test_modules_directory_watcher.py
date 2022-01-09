# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
from pathlib import Path
from shutil import move
from typing import Iterator
from unittest.mock import AsyncMock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from py._path.local import LocalPath
from simcore_service_dynamic_sidecar.modules import directory_watcher
from simcore_service_dynamic_sidecar.modules.directory_watcher import (
    DirectoryWatcherObservers,
)

# TODO:
# - setup and look at a directory
# - do something on that dir when file changes
# - use a mock to check that it calls the function a certain amount of times
# - good way to check the code works properly
# - todo make it run on a separate thread, already there
# - todo use absolute patterns for monitoring

pytestmark = pytest.mark.asyncio

TICK_INTERVAL = 0.001

# FIXTURES


@pytest.fixture
def patch_directory_watcher(monkeypatch: MonkeyPatch) -> Iterator[AsyncMock]:
    mocked_upload_data = AsyncMock(return_value=None)

    monkeypatch.setattr(directory_watcher, "DETECTION_INTERVAL", TICK_INTERVAL)
    monkeypatch.setattr(
        directory_watcher, "push_directory_via_nodeports", mocked_upload_data
    )

    yield mocked_upload_data


@pytest.fixture
def temp_dir(tmpdir: LocalPath) -> Path:
    return Path(tmpdir)


# UTILS


async def _generate_event_burst(temp_dir: Path, subfolder: str = None) -> None:
    full_dir_path = temp_dir if subfolder is None else temp_dir / subfolder
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


# TESTS


async def test_run_observer(
    patch_directory_watcher: AsyncMock,
    temp_dir: Path,
) -> None:

    directory_watcher_observers = DirectoryWatcherObservers()
    directory_watcher_observers.observe_directory(temp_dir)

    directory_watcher_observers.start()
    directory_watcher_observers.start()

    await asyncio.sleep(TICK_INTERVAL)

    # generates the first event chain
    await _generate_event_burst(temp_dir)

    await asyncio.sleep(2)

    # generates the second event chain
    await _generate_event_burst(temp_dir, "ciao")

    await directory_watcher_observers.stop()
    await directory_watcher_observers.stop()

    # pylint: disable=protected-access
    assert directory_watcher_observers._keep_running is False
    assert directory_watcher_observers._blocking_task is None

    assert patch_directory_watcher.call_count == 2
