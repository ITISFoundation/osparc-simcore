# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import errno
import multiprocessing
import multiprocessing.queues
import os as blocking_os
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from queue import Empty as QueueEmpty
from random import randbytes, shuffle
from shutil import move, rmtree
from threading import Event as ThreadingEvent
from threading import Thread
from time import sleep as blocking_sleep
from typing import Any, Final
from unittest.mock import AsyncMock

import aiofiles
import pytest
from aiofiles import os
from faker import Faker
from models_library.services import ServiceRunID
from pydantic import (
    ByteSize,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    TypeAdapter,
)
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes
from simcore_service_dynamic_sidecar.modules.notifications._notifications_ports import (
    PortNotifier,
)
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
from simcore_service_dynamic_sidecar.modules.outputs._event_handler import (
    _HEART_BEAT_MARK,
    _PortKeysEventHandler,
)
from simcore_service_dynamic_sidecar.modules.outputs._manager import OutputsManager
from simcore_service_dynamic_sidecar.modules.outputs._watchdog_extensions import (
    ExtendedInotifyObserver,
)
from simcore_service_dynamic_sidecar.modules.outputs._watcher import OutputsWatcher
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from watchdog.observers.inotify_c import Inotify

_TENACITY_RETRY_PARAMS: Final[dict[str, Any]] = {
    "reraise": True,
    "retry": retry_if_exception_type(AssertionError),
    "wait": wait_fixed(0.01),
    "stop": stop_after_delay(10),
}

_TICK_INTERVAL: Final[PositiveFloat] = 0.001
_WAIT_INTERVAL: Final[PositiveFloat] = _TICK_INTERVAL * 10
_UPLOAD_DURATION: Final[PositiveFloat] = _TICK_INTERVAL * 10


# FIXTURES


@pytest.fixture
def mounted_volumes(faker: Faker, tmp_path: Path) -> Iterator[MountedVolumes]:
    mounted_volumes = MountedVolumes(
        service_run_id=ServiceRunID.get_resource_tracking_run_id_for_dynamic(),
        node_id=faker.uuid4(cast_to=None),
        inputs_path=tmp_path / "inputs",
        outputs_path=tmp_path / "outputs",
        user_preferences_path=None,
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
async def outputs_context(mounted_volumes: MountedVolumes, port_keys: list[str]) -> OutputsContext:
    outputs_context = OutputsContext(outputs_path=mounted_volumes.disk_outputs_path)
    await outputs_context.set_file_type_port_keys(port_keys)
    return outputs_context


@pytest.fixture
async def outputs_manager(
    outputs_context: OutputsContext, port_notifier: PortNotifier
) -> AsyncIterable[OutputsManager]:
    outputs_manager = OutputsManager(
        outputs_context=outputs_context,
        port_notifier=port_notifier,
        io_log_redirect_cb=None,
        task_monitor_interval_s=_TICK_INTERVAL,
        progress_cb=None,
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
    mocker.patch.object(outputs_watcher_core, "DEFAULT_OBSERVER_TIMEOUT", _TICK_INTERVAL)
    outputs_watcher = OutputsWatcher(outputs_manager=outputs_manager, outputs_context=outputs_context)
    await outputs_watcher.start()
    yield outputs_watcher
    await outputs_watcher.shutdown()


@pytest.fixture
def mock_event_filter_upload_trigger(mocker: MockerFixture, outputs_watcher: OutputsWatcher) -> AsyncMock:
    mock_enqueue = AsyncMock(return_value=None)

    mocker.patch.object(
        outputs_watcher._event_filter.outputs_manager,  # noqa: SLF001
        "port_key_content_changed",
        mock_enqueue,
    )

    class FastDelayPolicy(BaseDelayPolicy):
        def get_min_interval(self) -> NonNegativeFloat:
            return _WAIT_INTERVAL

        def get_wait_interval(self, _: NonNegativeInt) -> NonNegativeFloat:
            return _WAIT_INTERVAL

    outputs_watcher._event_filter.delay_policy = FastDelayPolicy()  # noqa: SLF001

    return mock_enqueue


@pytest.fixture
def mock_long_running_upload_outputs(mocker: MockerFixture) -> Iterator[AsyncMock]:
    async def mock_upload_outputs(*args, **kwargs) -> None:
        await asyncio.sleep(_UPLOAD_DURATION)

    return mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager.upload_outputs",
        side_effect=mock_upload_outputs,
    )


@pytest.fixture(params=[1, 2, 4])
def files_per_port_key(request: pytest.FixtureRequest) -> NonNegativeInt:
    return request.param


@dataclass
class FileGenerationInfo:
    size: NonNegativeInt
    chunk_size: NonNegativeInt


@pytest.fixture(
    params=[
        FileGenerationInfo(
            size=TypeAdapter(ByteSize).validate_python("100b"),
            chunk_size=TypeAdapter(ByteSize).validate_python("1b"),
        ),
        FileGenerationInfo(
            size=TypeAdapter(ByteSize).validate_python("100kib"),
            chunk_size=TypeAdapter(ByteSize).validate_python("1kib"),
        ),
        FileGenerationInfo(
            size=TypeAdapter(ByteSize).validate_python("100mib"),
            chunk_size=TypeAdapter(ByteSize).validate_python("1mib"),
        ),
        FileGenerationInfo(
            size=TypeAdapter(ByteSize).validate_python("100mib"),
            chunk_size=TypeAdapter(ByteSize).validate_python("10mib"),
        ),
    ]
)
def file_generation_info(request: pytest.FixtureRequest) -> FileGenerationInfo:
    return request.param


# UTILS


async def _random_events_in_path(
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
        assert await os.path.exists(file_path) is False
        async with aiofiles.open(file_path, "wb"):
            pass
        assert await os.path.exists(file_path) is True

    async def _random_file(
        file_path: Path,
        *,
        size: NonNegativeInt,
        chunk_size: NonNegativeInt,
    ) -> None:
        async with aiofiles.open(file_path, "wb") as file:
            for _ in range(size // chunk_size):
                await file.write(randbytes(chunk_size))  # noqa: S311
            await file.write(randbytes(size % chunk_size))  # noqa: S311
        assert (await os.stat(file_path)).st_size == size

    async def _move_existing_file(file_path: Path) -> None:
        await _empty_file(file_path)
        destination = file_path.parent / f"{file_path.name}_"
        await os.rename(file_path, destination)
        assert await os.path.exists(file_path) is False
        assert await os.path.exists(destination) is True

    async def _remove_file(file_path: Path) -> None:
        await _empty_file(file_path)
        await os.remove(file_path)
        assert await os.path.exists(file_path) is False

    event_awaitables: list[Awaitable] = [
        *(_empty_file(port_key_path / f"empty_file_{i}") for i in range(empty_files)),
        *(_move_existing_file(port_key_path / f"moved_file_{i}") for i in range(moved_files)),
        *(_remove_file(port_key_path / f"removed_file_{i}") for i in range(removed_files)),
        *(
            _random_file(port_key_path / f"big_file{i}", size=size, chunk_size=chunk_size)
            for i in range(files_per_port_key)
        ),
    ]

    shuffle(event_awaitables)
    # NOTE: wait for events to be generated events in sequence
    # this is the worst case scenario and will catch more issues
    for awaitable in event_awaitables:
        await awaitable


async def _generate_event_burst(path: Path, subfolder: str | None = None) -> None:
    event = asyncio.Event()

    def _worker() -> None:
        full_dir_path = path if subfolder is None else path / subfolder
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
        event.set()

    thread = Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()
    await event.wait()


async def _wait_for_events_to_trigger() -> None:
    event_wait_interval = _WAIT_INTERVAL * 10 + 1
    print("WAIT FOR", event_wait_interval)
    await asyncio.sleep(event_wait_interval)


# TESTS


async def test_run_observer(
    mock_event_filter_upload_trigger: AsyncMock,
    outputs_watcher: OutputsWatcher,
    port_keys: list[str],
    wait_for_command_delivered: Callable[[OutputsContext], Awaitable[None]],
) -> None:
    await _wait_for_events_to_trigger()
    await outputs_watcher.enable_event_propagation()
    await wait_for_command_delivered(outputs_watcher.outputs_context)

    outputs_path = outputs_watcher.outputs_context.outputs_path

    # generates the first event chain
    await _wait_for_watch_registration_trigger(mock_event_filter_upload_trigger, outputs_path, port_keys[0])
    await _generate_event_burst(outputs_path, port_keys[0])

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)
            assert _get_notified_port_keys(mock_event_filter_upload_trigger) == {port_keys[0]}

    # generates the second event chain
    await _wait_for_watch_registration_trigger(mock_event_filter_upload_trigger, outputs_path, port_keys[1])
    await _generate_event_burst(outputs_path, port_keys[1])
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)
            assert _get_notified_port_keys(mock_event_filter_upload_trigger) == {port_keys[1]}


async def test_does_not_trigger_on_attribute_change(
    mock_event_filter_upload_trigger: AsyncMock,
    mounted_volumes: MountedVolumes,
    port_keys: list[str],
    outputs_watcher: OutputsWatcher,
    wait_for_command_delivered: Callable[[OutputsContext], Awaitable[None]],
):
    await _wait_for_events_to_trigger()
    await outputs_watcher.enable_event_propagation()
    await wait_for_command_delivered(outputs_watcher.outputs_context)

    # crate a file in the directory
    mounted_volumes.disk_outputs_path.mkdir(parents=True, exist_ok=True)
    file_path_1 = mounted_volumes.disk_outputs_path / port_keys[0] / "file1.txt"
    file_path_1.parent.mkdir(parents=True, exist_ok=True)
    file_path_1.touch()

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)
            assert mock_event_filter_upload_trigger.call_count == 1

    # apply an attribute change
    file_path_1.chmod(0o744)

    # same call count as before, event was ignored
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)
            assert mock_event_filter_upload_trigger.call_count == 1


async def test_port_key_sequential_event_generation(
    mock_long_running_upload_outputs: AsyncMock,
    mounted_volumes: MountedVolumes,
    outputs_watcher: OutputsWatcher,
    files_per_port_key: NonNegativeInt,
    file_generation_info: FileGenerationInfo,
    port_keys: list[str],
    wait_for_command_delivered: Callable[[OutputsContext], Awaitable[None]],
):
    await outputs_watcher.enable_event_propagation()
    await wait_for_command_delivered(outputs_watcher.outputs_context)

    # writing ports sequentially
    wait_interval_for_port: list[float] = []
    for port_key in port_keys:
        port_dir = mounted_volumes.disk_outputs_path / port_key
        port_dir.mkdir(parents=True, exist_ok=True)
        await _random_events_in_path(
            port_key_path=port_dir,
            files_per_port_key=files_per_port_key,
            size=file_generation_info.size,
            chunk_size=file_generation_info.chunk_size,
        )
        wait_interval_for_port.append(
            outputs_watcher._event_filter.delay_policy.get_wait_interval(  # noqa: SLF001
                get_directory_total_size(port_dir)
            )
        )

    # Waiting for events to finish propagation and changes to be uploaded
    MARGIN_FOR_ALL_EVENT_PROCESSORS_TO_TRIGGER = 1
    sleep_for = max(max(wait_interval_for_port) + MARGIN_FOR_ALL_EVENT_PROCESSORS_TO_TRIGGER, 3)
    print(f"max {sleep_for=} interval")
    async for attempt in AsyncRetrying(**{**_TENACITY_RETRY_PARAMS, "stop": stop_after_delay(sleep_for)}):
        with attempt:
            await asyncio.sleep(0)
            assert mock_long_running_upload_outputs.call_count > 0

    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0)
            uploaded_port_keys: set[str] = set()
            for call_args in mock_long_running_upload_outputs.call_args_list:
                uploaded_port_keys |= set(call_args.kwargs["port_keys"])
            assert uploaded_port_keys == set(port_keys)


# KNOWN LIMITATIONS
#
# The tests below document notification gaps which are currently inherent to
# the inotify-based outputs watcher. They are expected to start passing (XPASS)
# once the watcher hardens, e.g. by bounding the per-port-key notification
# state, retrying and surfacing failed inotify_add_watch calls, and stopping
# the heart-beats when an event thread dies.
#
# Not listed here: writes that appear and disappear in a new port-key directory
# before the emitter registers its watch are never seen by inotify. This is
# accepted by design: notifications only trigger uploads, which read the current
# directory contents, so a write that no longer exists has nothing to upload.


# enough files to overflow the notification path while its consumer is stalled
_EVENT_STORM_FILES: Final[int] = 4_000


def _get_notified_port_keys(mock_upload_trigger: AsyncMock) -> set[str]:
    return {call.args[0] for call in mock_upload_trigger.call_args_list}


def _touch_watch_canary(outputs_path: Path, port_key: str, *, canary_name: str = ".watch_canary") -> None:
    """Create a port-key directory and a file in it that stays on disk. The
    emitter registers the inotify watch for a new directory only while it
    processes the directory's creation event, and the kernel drops all earlier
    events in it. The canary yields a notification under either timing: the
    kernel records it when it lands after the watch, and watchdog's scan when
    adding the watch reports it when it lands before. Observing the
    notification proves the watch is active, which no amount of sleeping can
    guarantee.
    """
    port_key_dir = outputs_path / port_key
    port_key_dir.mkdir(parents=True, exist_ok=True)
    (port_key_dir / canary_name).touch()


async def _wait_for_watch_registration_trigger(
    upload_trigger: AsyncMock, outputs_path: Path, port_key: str, *, canary_name: str = ".watch_canary"
) -> None:
    _touch_watch_canary(outputs_path, port_key, canary_name=canary_name)
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0.05)
            assert port_key in _get_notified_port_keys(upload_trigger)
    upload_trigger.reset_mock()


async def _wait_for_watch_registration_queue(
    queue: multiprocessing.queues.Queue[str | None],
    outputs_path: Path,
    port_key: str,
    *,
    canary_name: str = ".watch_canary",
) -> None:
    _touch_watch_canary(outputs_path, port_key, canary_name=canary_name)
    async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
        with attempt:
            await asyncio.sleep(0.05)
            assert port_key in _drain_nowait(queue)


def _drain_nowait[T](queue: multiprocessing.queues.Queue[T]) -> list[T]:
    drained: list[T] = []
    while True:
        try:
            drained.append(queue.get_nowait())
        except QueueEmpty:
            return drained


@pytest.fixture
async def drain_port_key_events_on_teardown(outputs_watcher: OutputsWatcher) -> AsyncIterator[None]:
    """prevents a teardown deadlock: with propagation left enabled the queues keep
    backlogging notifications, and the multiprocessing queue feeder thread then
    blocks forever at interpreter exit
    """
    yield
    await outputs_watcher.disable_event_propagation()
    queue = outputs_watcher.outputs_context.port_key_events_queue
    await asyncio.to_thread(_drain_queue, queue)


def _drain_queue(queue: multiprocessing.queues.Queue) -> None:
    while True:
        try:
            queue.get_nowait()
        except QueueEmpty:
            return


@pytest.mark.xfail(
    strict=False,
    reason="port_key_events_queue is unbounded and receives one entry per raw file "
    "event: while the consumer is stalled it backlogs thousands of redundant "
    "notifications for the same port key instead of coalescing them (OOM risk)",
)
async def test_notification_queue_stays_bounded_under_event_storm(
    mock_event_filter_upload_trigger: AsyncMock,
    mocker: MockerFixture,
    outputs_watcher: OutputsWatcher,
    port_keys: list[str],
    drain_port_key_events_on_teardown: None,
    wait_for_command_delivered: Callable[[OutputsContext], Awaitable[None]],
) -> None:
    await _wait_for_events_to_trigger()
    await outputs_watcher.enable_event_propagation()
    await wait_for_command_delivered(outputs_watcher.outputs_context)

    outputs_path = outputs_watcher.outputs_context.outputs_path
    noisy_port_key, quiet_port_key = port_keys[0], port_keys[1]

    # ensure the emitter registered the watches before generating any events
    await _wait_for_watch_registration_trigger(mock_event_filter_upload_trigger, outputs_path, noisy_port_key)
    await _wait_for_watch_registration_trigger(mock_event_filter_upload_trigger, outputs_path, quiet_port_key)

    # stall the consumer so nothing drains the queue while the storm runs
    block_enqueue = asyncio.Event()
    mocker.patch.object(
        outputs_watcher._event_filter,  # noqa: SLF001
        "enqueue",
        AsyncMock(side_effect=block_enqueue.wait),
    )

    def _flood_with_files() -> None:
        for i in range(_EVENT_STORM_FILES):
            (outputs_path / noisy_port_key / f"file_{i}").touch()

    await asyncio.to_thread(_flood_with_files)
    (outputs_path / quiet_port_key / "output.dat").write_bytes(b"result")

    # let the watcher process drain the kernel queue into its buffer
    await asyncio.sleep(1)
    backlog = outputs_watcher.outputs_context.port_key_events_queue.qsize()

    block_enqueue.set()

    # no notification may be lost while the queue is backed up
    async for attempt in AsyncRetrying(**{**_TENACITY_RETRY_PARAMS, "stop": stop_after_delay(30)}):
        with attempt:
            await asyncio.sleep(0)
            notified_port_keys = _get_notified_port_keys(mock_event_filter_upload_trigger)
            assert {noisy_port_key, quiet_port_key} <= notified_port_keys

    # a sane design coalesces per port key, so the backlog must not grow with
    # the number of raw file events
    assert backlog < 2 * len(port_keys)


_WATCH_LIMIT_PORT_KEY: Final[str] = "port_key_watch_limit"


@pytest.fixture
def patch_watch_registration_enospc(mocker: MockerFixture) -> None:
    """makes watch registration for `_WATCH_LIMIT_PORT_KEY` fail with ENOSPC,
    simulating an exhausted fs.inotify.max_user_watches quota
    """
    original_add_watch = Inotify._add_watch  # noqa: SLF001

    def _raise_on_watch_limit(self: Inotify, path: bytes, mask: int) -> int:
        if Path(path.decode()).name == _WATCH_LIMIT_PORT_KEY:
            raise OSError(errno.ENOSPC, "inotify watch limit reached")
        return original_add_watch(self, path, mask)

    mocker.patch.object(Inotify, "_add_watch", autospec=True, side_effect=_raise_on_watch_limit)


@pytest.mark.xfail(
    strict=True,
    reason="when inotify_add_watch fails watchdog skips the directory and never "
    "retries it: the file changes inside stay invisible, no notification is ever "
    "delivered for that port key, and the degraded watcher is never surfaced",
)
async def test_watch_registration_failure_does_not_silently_kill_notifications(
    patch_watch_registration_enospc: None,
    tmp_path: Path,
) -> None:
    # NOTE: unlike in the sidecar, the observer here runs in the test process: with
    # the forkserver start method the watcher process re-imports modules, so the
    # ENOSPC patch would never reach it. The port-key events queue is the same
    # notification boundary the watcher process uses to reach the main process.
    outputs_root = tmp_path / "outputs_root"
    outputs_root.mkdir()

    port_key_events_queue: multiprocessing.queues.Queue[str | None] = multiprocessing.get_context().Queue()

    event_handler = _PortKeysEventHandler(outputs_root, port_key_events_queue)
    event_handler.handle_toggle_event_propagation(is_enabled=True)
    regular_port_key = "regular_port_key"
    event_handler.handle_set_outputs_port_keys(outputs_port_keys={_WATCH_LIMIT_PORT_KEY, regular_port_key})

    observer = ExtendedInotifyObserver()
    observer.schedule(event_handler, str(outputs_root), recursive=True)
    observer.start()
    try:
        # sanity check: the canary of a regularly watched port key gets notified,
        # which also proves its watch is registered before the next step
        await _wait_for_watch_registration_queue(port_key_events_queue, outputs_root, regular_port_key)

        # the watch registration for this directory fails with ENOSPC: its content
        # changes must either still be delivered or surface a degraded watcher,
        # but today the directory is left permanently unwatched and they are lost
        await _wait_for_watch_registration_queue(port_key_events_queue, outputs_root, _WATCH_LIMIT_PORT_KEY)
    finally:
        observer.stop()
        observer.join()


# shorter than the production heart-beat interval, only used to observe that
# heart-beats keep flowing after the event thread dies
_HEART_BEAT_INTERVAL_S: Final[PositiveFloat] = 0.1


@pytest.mark.xfail(
    strict=True,
    reason="the watcher heart-beats from its process main loop, so an unhandled "
    "error in the inotify read thread stops every notification while the health "
    "check keeps receiving heart-beats and never restarts the watcher",
)
async def test_dead_event_thread_does_not_silently_stop_notifications(
    tmp_path: Path,
) -> None:
    # NOTE: in-process like the watch-registration test, reproducing the two
    # channels the watcher process shares with the main process: the port-key
    # events queue and the health-check heart-beats of _process_worker.
    outputs_root = tmp_path / "outputs_root"
    outputs_root.mkdir()

    port_key = "port_key"
    port_key_events_queue: multiprocessing.queues.Queue[str | None] = multiprocessing.get_context().Queue()
    health_check_queue: multiprocessing.queues.Queue[int | None] = multiprocessing.get_context().Queue()

    event_handler = _PortKeysEventHandler(outputs_root, port_key_events_queue)
    event_handler.handle_toggle_event_propagation(is_enabled=True)
    event_handler.handle_set_outputs_port_keys(outputs_port_keys={port_key})

    # the watcher process main loop sends heart-beats independently of the
    # observer threads
    stop_heart_beats = ThreadingEvent()

    def _heart_beat_loop() -> None:
        while not stop_heart_beats.is_set():
            health_check_queue.put(_HEART_BEAT_MARK)
            blocking_sleep(_HEART_BEAT_INTERVAL_S)

    heart_beat_thread = Thread(target=_heart_beat_loop, daemon=True)

    observer = ExtendedInotifyObserver()
    observer.schedule(event_handler, str(outputs_root), recursive=True)
    observer.start()
    heart_beat_thread.start()
    try:
        # sanity check: notifications flow while everything is healthy, and the
        # canary wait proves the watch is registered before the next steps
        await _wait_for_watch_registration_queue(port_key_events_queue, outputs_root, port_key)

        # simulate an unhandled error in the inotify read loop: the read thread
        # dies and with it every further notification
        emitter = next(iter(observer.emitters))
        # pylint: disable-next=pointless-statement
        assert (read_thread := emitter._inotify) is not None  # pyright: ignore[reportAttributeAccessIssue] # noqa: RUF018, SLF001
        inotify = read_thread._inotify  # noqa: SLF001

        def _raise_io_error() -> bool:
            raise OSError(errno.EIO, "simulated inotify read failure")

        inotify._check_inotify_fd = _raise_io_error  # noqa: SLF001
        # the read thread is parked inside poll(), so waking it with the kill
        # channel makes it re-enter _check_inotify_fd (now raising) and die
        blocking_os.write(inotify._kill_w, b"!")  # noqa: SLF001
        async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
            with attempt:
                await asyncio.sleep(0.1)
                assert not read_thread.is_alive()

        # the health check keeps receiving heart-beats and considers the watcher
        # perfectly healthy: drop the marks sent before the thread died first
        _ = _drain_nowait(health_check_queue)
        await asyncio.sleep(5 * _HEART_BEAT_INTERVAL_S)
        assert _drain_nowait(health_check_queue).count(_HEART_BEAT_MARK) >= 2

        # yet the watcher is dead: further changes must either still be delivered
        # or surface the degraded watcher, today they are lost silently
        await _wait_for_watch_registration_queue(
            port_key_events_queue,
            outputs_root,
            port_key,
            canary_name=".watch_canary_after_death",
        )
    finally:
        stop_heart_beats.set()
        observer.stop()
        observer.join()
