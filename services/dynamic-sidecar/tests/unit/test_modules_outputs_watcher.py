# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from random import randbytes, shuffle
from shutil import move, rmtree
from threading import Thread
from typing import AsyncIterable, AsyncIterator, Awaitable, Final, Iterator, Optional
from unittest.mock import AsyncMock

import aiofiles
import pytest
from aiofiles import os
from faker import Faker
from pydantic import (
    ByteSize,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    parse_obj_as,
)
from pytest import FixtureRequest
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes
from simcore_service_dynamic_sidecar.modules.outputs import (
    _watcher as outputs_watcher_core,
)
from simcore_service_dynamic_sidecar.modules.outputs._context import OutputsContext
from simcore_service_dynamic_sidecar.modules.outputs._directory_utils import (
    get_directory_total_size,
)
from simcore_service_dynamic_sidecar.modules.outputs._event_filter import (
    BaseDelayPolicy,
)
from simcore_service_dynamic_sidecar.modules.outputs._manager import OutputsManager
from simcore_service_dynamic_sidecar.modules.outputs._watcher import OutputsWatcher

TICK_INTERVAL: Final[PositiveFloat] = 0.001
WAIT_INTERVAL: Final[PositiveFloat] = TICK_INTERVAL * 10
UPLOAD_DURATION: Final[PositiveFloat] = TICK_INTERVAL * 10


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
def port_keys() -> list[str]:
    return [f"port_key_{x}" for x in range(4)]


@pytest.fixture
async def outputs_context(
    mounted_volumes: MountedVolumes, port_keys: list[str]
) -> OutputsContext:
    outputs_context = OutputsContext(outputs_path=mounted_volumes.disk_outputs_path)
    await outputs_context.set_file_type_port_keys(port_keys)
    return outputs_context


@pytest.fixture
async def outputs_manager(
    outputs_context: OutputsContext,
) -> AsyncIterable[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_context=outputs_context,
        io_log_redirect_cb=None,
        task_monitor_interval_s=TICK_INTERVAL,
    )
    await outputs_manager.start()
    yield outputs_manager
    await outputs_manager.shutdown()


@pytest.fixture
async def outputs_watcher(
    mocker: MockerFixture,
    outputs_context: OutputsContext,
    outputs_manager: OutputsManager,
) -> AsyncIterator[OutputsWatcher]:
    mocker.patch.object(outputs_watcher_core, "DEFAULT_OBSERVER_TIMEOUT", TICK_INTERVAL)
    outputs_watcher = OutputsWatcher(
        outputs_manager=outputs_manager, outputs_context=outputs_context
    )
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
        "port_key_content_changed",
        mock_enqueue,
    )

    class FastDelayPolicy(BaseDelayPolicy):
        def get_min_interval(self) -> NonNegativeFloat:
            return WAIT_INTERVAL

        def get_wait_interval(self, dir_size: NonNegativeInt) -> NonNegativeFloat:
            return WAIT_INTERVAL

    outputs_watcher._event_filter.delay_policy = FastDelayPolicy()

    yield mock_enqueue


@pytest.fixture
def mock_long_running_upload_outputs(mocker: MockerFixture) -> Iterator[AsyncMock]:
    async def mock_upload_outputs(*args, **kwargs) -> None:
        await asyncio.sleep(UPLOAD_DURATION)

    yield mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager.upload_outputs",
        sire_effect=mock_upload_outputs,
    )


@pytest.fixture(params=[1, 2, 4])
def files_per_port_key(request: FixtureRequest) -> NonNegativeInt:
    return request.param


@dataclass
class FileGenerationInfo:
    size: NonNegativeInt
    chunk_size: NonNegativeInt


@pytest.fixture(
    params=[
        FileGenerationInfo(
            size=parse_obj_as(ByteSize, "100b"),
            chunk_size=parse_obj_as(ByteSize, "1b"),
        ),
        FileGenerationInfo(
            size=parse_obj_as(ByteSize, "100kib"),
            chunk_size=parse_obj_as(ByteSize, "1kib"),
        ),
        FileGenerationInfo(
            size=parse_obj_as(ByteSize, "100mib"),
            chunk_size=parse_obj_as(ByteSize, "1mib"),
        ),
        FileGenerationInfo(
            size=parse_obj_as(ByteSize, "100mib"),
            chunk_size=parse_obj_as(ByteSize, "10mib"),
        ),
    ]
)
def file_generation_info(request: FixtureRequest) -> FileGenerationInfo:
    return request.param


# UTILS


async def random_events_in_path(
    *,
    port_key_path: Path,
    files_per_port_key: NonNegativeInt,
    size: NonNegativeInt,
    chunk_size: NonNegativeInt,
    empty_files: NonNegativeInt = 10,
    moved_files: NonNegativeInt = 10,
    removed_files: NonNegativeInt = 10,
) -> None:
    """
    Simulates some random user activity"""

    async def _empty_file(file_path: Path) -> None:
        assert file_path.exists() is False
        async with aiofiles.open(file_path, "wb"):
            pass
        assert file_path.exists() is True

    async def _random_file(
        file_path: Path,
        *,
        size: NonNegativeInt,
        chunk_size: NonNegativeInt,
    ) -> None:
        async with aiofiles.open(file_path, "wb") as file:
            for _ in range(size // chunk_size):
                await file.write(randbytes(chunk_size))
            await file.write(randbytes(size % chunk_size))
        assert file_path.stat().st_size == size

    async def _move_existing_file(file_path: Path) -> None:
        await _empty_file(file_path)
        destination = file_path.parent / f"{file_path.name}_"
        await os.rename(file_path, destination)
        assert file_path.exists() is False
        assert destination.exists() is True

    async def _remove_file(file_path: Path) -> None:
        await _empty_file(file_path)
        await os.remove(file_path)
        assert file_path.exists() is False

    event_awaitables: deque[Awaitable] = deque()

    for i in range(empty_files):
        event_awaitables.append(_empty_file(port_key_path / f"empty_file_{i}"))
    for i in range(moved_files):
        event_awaitables.append(_move_existing_file(port_key_path / f"moved_file_{i}"))
    for i in range(removed_files):
        event_awaitables.append(_remove_file(port_key_path / f"removed_file_{i}"))

    for i in range(files_per_port_key):
        event_awaitables.append(
            _random_file(
                port_key_path / f"big_file{i}", size=size, chunk_size=chunk_size
            )
        )

    shuffle(event_awaitables)
    # NOTE: wait for events to be generated events in sequence
    # this is the worst case scenario and will catch more issues
    for awaitable in event_awaitables:
        await awaitable


async def _generate_event_burst(
    tmp_path: Path, subfolder: Optional[str] = None
) -> None:
    def _worker():
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

    thread = Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()


async def _wait_for_events_to_trigger() -> None:
    event_wait_interval = WAIT_INTERVAL * 10 + 1
    print("WAIT FOR", event_wait_interval)
    await asyncio.sleep(event_wait_interval)


async def test_run_observer(
    mock_event_filter_upload_trigger: AsyncMock,
    outputs_watcher: OutputsWatcher,
    port_keys: list[str],
) -> None:
    # generates the first event chain
    await _generate_event_burst(
        outputs_watcher.outputs_context.outputs_path, port_keys[0]
    )
    await _wait_for_events_to_trigger()
    assert mock_event_filter_upload_trigger.call_count == 1

    # generates the second event chain
    await _generate_event_burst(
        outputs_watcher.outputs_context.outputs_path, port_keys[1]
    )
    await _wait_for_events_to_trigger()
    assert mock_event_filter_upload_trigger.call_count == 2


async def test_does_not_trigger_on_attribute_change(
    mock_event_filter_upload_trigger: AsyncMock,
    mounted_volumes: MountedVolumes,
    port_keys: list[str],
    outputs_watcher: OutputsWatcher,
):
    await _wait_for_events_to_trigger()

    # crate a file in the directory
    mounted_volumes.disk_outputs_path.mkdir(parents=True, exist_ok=True)
    file_path_1 = mounted_volumes.disk_outputs_path / port_keys[0] / "file1.txt"
    file_path_1.parent.mkdir(parents=True, exist_ok=True)
    file_path_1.touch()

    await _wait_for_events_to_trigger()
    assert mock_event_filter_upload_trigger.call_count == 1

    # apply an attribute change
    file_path_1.chmod(0o744)

    await _wait_for_events_to_trigger()
    # same call count as before, event was ignored
    assert mock_event_filter_upload_trigger.call_count == 1


async def test_port_key_sequential_event_generation(
    mock_long_running_upload_outputs: AsyncMock,
    mounted_volumes: MountedVolumes,
    outputs_watcher: OutputsWatcher,
    files_per_port_key: NonNegativeInt,
    file_generation_info: FileGenerationInfo,
    port_keys: list[str],
):
    # writing ports sequentially
    wait_interval_for_port: deque[float] = deque()
    for port_key in port_keys:
        port_dir = mounted_volumes.disk_outputs_path / port_key
        port_dir.mkdir(parents=True, exist_ok=True)
        await random_events_in_path(
            port_key_path=port_dir,
            files_per_port_key=files_per_port_key,
            size=file_generation_info.size,
            chunk_size=file_generation_info.chunk_size,
        )
        wait_interval_for_port.append(
            outputs_watcher._event_filter.delay_policy.get_wait_interval(
                get_directory_total_size(port_dir)
            )
        )

    # Waiting for events o finish propagation and changes to be uploaded
    MARGIN_FOR_ALL_EVENT_PROCESSORS_TO_TRIGGER = 1
    sleep_for = max(wait_interval_for_port) + MARGIN_FOR_ALL_EVENT_PROCESSORS_TO_TRIGGER
    print(f"Waiting {sleep_for} seconds for events to be processed")
    await asyncio.sleep(sleep_for)

    assert mock_long_running_upload_outputs.call_count > 0
    uploaded_port_keys: set[str] = set()
    for call_args in mock_long_running_upload_outputs.call_args_list:
        uploaded_port_keys.update(call_args.kwargs["port_keys"])

    assert uploaded_port_keys == set(port_keys)
