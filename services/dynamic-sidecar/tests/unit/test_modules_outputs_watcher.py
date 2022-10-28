# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from pathlib import Path
from shutil import move, rmtree
from typing import AsyncIterable, AsyncIterator, Iterator, Optional
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from pydantic import NonNegativeFloat, NonNegativeInt
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes
from simcore_service_dynamic_sidecar.modules.outputs_manager import OutputsManager
from simcore_service_dynamic_sidecar.modules.outputs_watcher import (
    _core as outputs_watcher_core,
)
from simcore_service_dynamic_sidecar.modules.outputs_watcher._core import OutputsWatcher
from simcore_service_dynamic_sidecar.modules.outputs_watcher._event_filter import (
    BaseDelayPolicy,
)
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT

TICK_INTERVAL = 0.001
WAIT_INTERVAL = TICK_INTERVAL * 10

# FIXTURES


@pytest.fixture
def mounted_volumes(faker: Faker, tmp_path: Path) -> Iterator[MountedVolumes]:
    mounted_volumes = MountedVolumes(
        run_id=faker.uuid4(cast_to=None),
        node_id=faker.uuid4(cast_to=None),
        inputs_path=tmp_path / "inputs",
        outputs_path=tmp_path / "outputs",
        state_paths=[],
        state_exclude=set(),
        compose_namespace="",
        dy_volumes=tmp_path,
    )
    yield mounted_volumes
    rmtree(tmp_path)


@pytest.fixture
async def outputs_manager(
    mounted_volumes: MountedVolumes,
) -> AsyncIterable[OutputsManager]:
    outputs_manager = OutputsManager(outputs_path=mounted_volumes.disk_outputs_path)
    outputs_manager.outputs_port_keys.add("first_test")
    outputs_manager.outputs_port_keys.add("second_test")
    yield outputs_manager
    await outputs_manager.shutdown()


@pytest.fixture
async def outputs_watcher(
    mocker: MockerFixture,
    mounted_volumes: MountedVolumes,
    outputs_manager: OutputsManager,
) -> OutputsWatcher:
    mocker.patch.object(outputs_watcher_core, "DEFAULT_OBSERVER_TIMEOUT", TICK_INTERVAL)
    outputs_watcher = OutputsWatcher(
        outputs_manager=outputs_manager, io_log_redirect_cb=None
    )
    outputs_watcher.observe_outputs_directory(mounted_volumes.disk_outputs_path)

    return outputs_watcher


@pytest.fixture
async def running_outputs_watcher(
    outputs_watcher: OutputsWatcher,
) -> AsyncIterator[OutputsWatcher]:
    await outputs_watcher.start()
    yield outputs_watcher
    await outputs_watcher.shutdown()


@pytest.fixture
def mock_event_filter_upload_trigger(
    mocker: MockerFixture,
    outputs_watcher: OutputsWatcher,
) -> Iterator[AsyncMock]:
    mock_enqueue = AsyncMock(return_value=None)

    mocker.patch.object(
        outputs_watcher._event_filter.outputs_manager,
        "upload_after_port_change",
        mock_enqueue,
    )

    class FastDelayPolicy(BaseDelayPolicy):
        def get_min_interval(self) -> NonNegativeFloat:
            return WAIT_INTERVAL

        def get_wait_interval(self, dir_size: NonNegativeInt) -> NonNegativeFloat:
            return WAIT_INTERVAL

    outputs_watcher._event_filter.delay_policy = FastDelayPolicy()

    yield mock_enqueue


async def _generate_event_burst(
    tmp_path: Path, subfolder: Optional[str] = None
) -> None:
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
    await asyncio.sleep(WAIT_INTERVAL)


async def _wait_for_events_to_trigger() -> None:
    await asyncio.sleep(DEFAULT_OBSERVER_TIMEOUT + WAIT_INTERVAL)


async def test_run_observer(
    mock_event_filter_upload_trigger: AsyncMock,
    mounted_volumes: MountedVolumes,
    outputs_watcher: OutputsWatcher,
) -> None:

    assert outputs_watcher._outputs_event_handler
    assert (  # pylint:disable=protected-access
        outputs_watcher._outputs_event_handler._is_enabled is True
    )

    await outputs_watcher.start()
    await outputs_watcher.start()

    await _wait_for_events_to_trigger()

    # generates the first event chain
    await _generate_event_burst(mounted_volumes.disk_outputs_path, "first_test")

    await _wait_for_events_to_trigger()

    # generates the second event chain
    await _generate_event_burst(mounted_volumes.disk_outputs_path, "second_test")

    await outputs_watcher.shutdown()
    await outputs_watcher.shutdown()

    # pylint: disable=protected-access
    assert outputs_watcher._keep_running is False
    assert outputs_watcher._blocking_task is None

    assert mock_event_filter_upload_trigger.call_count == 2


async def test_does_not_trigger_on_attribute_change(
    mock_event_filter_upload_trigger: AsyncMock,
    mounted_volumes: MountedVolumes,
    running_outputs_watcher: OutputsWatcher,
):

    await asyncio.sleep(WAIT_INTERVAL)

    # crate a file in the directory
    mounted_volumes.disk_outputs_path.mkdir(parents=True, exist_ok=True)
    file_path_1 = mounted_volumes.disk_outputs_path / "first_test" / "file1.txt"
    file_path_1.parent.mkdir(parents=True, exist_ok=True)
    file_path_1.touch()

    await _wait_for_events_to_trigger()
    assert mock_event_filter_upload_trigger.call_count == 1

    # apply an attribute change
    file_path_1.chmod(0o744)

    await _wait_for_events_to_trigger()
    # same call count as before, event was ignored
    assert mock_event_filter_upload_trigger.call_count == 1


# TODO: write a test to simulate more impactful workload
# - have it write X files per directory sequentially
# - in total 10 directories
# - would like to detect that only 1 event per port key for upload was triggered

# TODO: run the above test in parallel
