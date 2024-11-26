import logging
from asyncio import CancelledError, Task, create_task, get_event_loop
from asyncio import sleep as async_sleep
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from queue import Empty
from threading import Thread
from time import sleep as blocking_sleep
from typing import Any, Final

import aioprocessing  # type: ignore [import-untyped]
from aioprocessing.process import AioProcess  # type: ignore [import-untyped]
from aioprocessing.queues import AioQueue  # type: ignore [import-untyped]
from pydantic import PositiveFloat
from servicelib.logging_utils import log_context
from watchdog.events import FileSystemEvent

from ._context import OutputsContext
from ._manager import OutputsManager
from ._watchdog_extensions import ExtendedInotifyObserver, SafeFileSystemEventHandler

_HEART_BEAT_MARK: Final = 1

_logger = logging.getLogger(__name__)


class _PortKeysEventHandler(SafeFileSystemEventHandler):
    # NOTE: runs in the created process

    def __init__(self, outputs_path: Path, port_key_events_queue: AioQueue):
        super().__init__()

        self._is_event_propagation_enabled: bool = False
        self.outputs_path: Path = outputs_path
        self.port_key_events_queue: AioQueue = port_key_events_queue
        self._outputs_port_keys: set[str] = set()

    def handle_set_outputs_port_keys(self, *, outputs_port_keys: set[str]) -> None:
        self._outputs_port_keys = outputs_port_keys

    def handle_toggle_event_propagation(self, *, is_enabled: bool) -> None:
        self._is_event_propagation_enabled = is_enabled

    def event_handler(self, event: FileSystemEvent) -> None:
        if not self._is_event_propagation_enabled:
            return

        # NOTE: ignoring all events which are not relative to modifying
        # the contents of the `port_key` folders from the outputs directory

        path_relative_to_outputs = Path(
            event.src_path.decode()
            if isinstance(event.src_path, bytes)
            else event.src_path
        ).relative_to(self.outputs_path)

        # discard event if not part of a subfolder
        relative_path_parents = path_relative_to_outputs.parents
        event_in_subdirs = len(relative_path_parents) > 0
        if not event_in_subdirs:
            return

        # only accept events generated inside `port_key` subfolder
        port_key_candidate = f"{relative_path_parents[0]}"

        if port_key_candidate in self._outputs_port_keys:
            # messages in this queue (part of the process),
            # will be consumed by the asyncio thread
            self.port_key_events_queue.put(port_key_candidate)


class _EventHandlerProcess:
    def __init__(
        self,
        outputs_context: OutputsContext,
        health_check_queue: AioQueue,
        heart_beat_interval_s: PositiveFloat,
    ) -> None:
        # NOTE: runs in asyncio thread

        self.outputs_context: OutputsContext = outputs_context
        self.health_check_queue: AioQueue = health_check_queue
        self.heart_beat_interval_s: PositiveFloat = heart_beat_interval_s

        # This is accessible from the creating process and from
        # the process itself and is used to stop the process.
        self._stop_queue: AioQueue = aioprocessing.AioQueue()

        self._file_system_event_handler: _PortKeysEventHandler | None = None
        self._process: AioProcess | None = None

    def start_process(self) -> None:
        # NOTE: runs in asyncio thread

        with log_context(
            _logger, logging.DEBUG, f"{_EventHandlerProcess.__name__} start_process"
        ):
            self._process = aioprocessing.AioProcess(
                target=self._process_worker, daemon=True
            )
            self._process.start()  # pylint:disable=no-member

    def stop_process(self) -> None:
        # NOTE: runs in asyncio thread

        with log_context(
            _logger, logging.DEBUG, f"{_EventHandlerProcess.__name__} stop_process"
        ):
            self._stop_queue.put(None)  # pylint:disable=no-member

            if self._process:
                # force stop the process
                self._process.kill()  # pylint:disable=no-member
                self._process.join()  # pylint:disable=no-member
                self._process = None

            # cleanup whatever remains
            self._file_system_event_handler = None

    def shutdown(self) -> None:
        # NOTE: runs in asyncio thread

        with log_context(
            _logger, logging.DEBUG, f"{_EventHandlerProcess.__name__} shutdown"
        ):
            self.stop_process()

            # signal queue observers to finish
            self.outputs_context.port_key_events_queue.put(
                None
            )  # pylint:disable=no-member
            self.health_check_queue.put(None)  # pylint:disable=no-member

    def _thread_worker_update_outputs_port_keys(self) -> None:
        # NOTE: runs as a thread in the created process

        # Propagate `outputs_port_keys` changes to the `_PortKeysEventHandler`.
        while True:
            message: dict[
                str, Any
            ] | None = (
                self.outputs_context.file_system_event_handler_queue.get()  # pylint:disable=no-member
            )
            _logger.debug("received message %s", message)

            # no more messages quitting
            if message is None:
                break

            # do nothing
            if self._file_system_event_handler is None:
                continue

            # handle events
            method_kwargs: dict[str, Any] = message["kwargs"]
            method_name = message["method_name"]
            method_to_call = getattr(self._file_system_event_handler, method_name)
            method_to_call(**method_kwargs)

    def _process_worker(self) -> None:
        # NOTE: runs in the created process

        observer = ExtendedInotifyObserver()
        self._file_system_event_handler = _PortKeysEventHandler(
            outputs_path=self.outputs_context.outputs_path,
            port_key_events_queue=self.outputs_context.port_key_events_queue,
        )
        watch = None

        thread_update_outputs_port_keys = Thread(
            target=self._thread_worker_update_outputs_port_keys, daemon=True
        )
        thread_update_outputs_port_keys.start()

        try:
            watch = observer.schedule(
                event_handler=self._file_system_event_handler,
                path=f"{self.outputs_context.outputs_path.absolute()}",
                recursive=True,
            )
            observer.start()

            while self._stop_queue.qsize() == 0:  # pylint:disable=no-member
                # watchdog internally uses 1 sec interval to detect events
                # sleeping for less is useless.
                # If this value is bigger then the DEFAULT_OBSERVER_TIMEOUT
                # the result will not be as expected. Keep sleep to 1 second

                # NOTE: watchdog will block this thread for some period of
                # time while handling inotify events
                # the health_check sending could be delayed

                self.health_check_queue.put(  # pylint:disable=no-member
                    _HEART_BEAT_MARK
                )
                blocking_sleep(self.heart_beat_interval_s)

        except Exception:  # pylint: disable=broad-except
            _logger.exception("Unexpected error")
        finally:
            if watch:
                observer.remove_handler_for_watch(
                    self._file_system_event_handler, watch
                )
            observer.stop()

            # stop created thread
            self.outputs_context.file_system_event_handler_queue.put(  # pylint:disable=no-member
                None
            )
            thread_update_outputs_port_keys.join()

            _logger.warning("%s exited", _EventHandlerProcess.__name__)


class EventHandlerObserver:
    """
    Ensures watchdog is not blocking.
    When blocking, it will restart the process handling the watchdog.
    """

    def __init__(
        self,
        outputs_context: OutputsContext,
        outputs_manager: OutputsManager,
        heart_beat_interval_s: PositiveFloat,
        *,
        max_heart_beat_wait_interval_s: PositiveFloat = 10,
    ) -> None:
        self.outputs_context: OutputsContext = outputs_context
        self.outputs_manager: OutputsManager = outputs_manager
        self.heart_beat_interval_s: PositiveFloat = heart_beat_interval_s
        self.max_heart_beat_wait_interval_s: PositiveFloat = (
            max_heart_beat_wait_interval_s
        )

        self._health_check_queue: AioQueue = aioprocessing.AioQueue()
        self._event_handler_process: _EventHandlerProcess = _EventHandlerProcess(
            outputs_context=outputs_context,
            health_check_queue=self._health_check_queue,
            heart_beat_interval_s=heart_beat_interval_s,
        )
        self._keep_running: bool = False
        self._task_health_worker: Task | None = None

    @property
    def wait_for_heart_beat_interval_s(self) -> PositiveFloat:
        return min(
            self.heart_beat_interval_s * 100, self.max_heart_beat_wait_interval_s
        )

    async def _health_worker(self) -> None:
        wait_for = self.wait_for_heart_beat_interval_s
        while self._keep_running:
            await async_sleep(wait_for)

            heart_beat_count = 0
            while True:
                try:
                    self._health_check_queue.get_nowait()  # pylint:disable=no-member
                    heart_beat_count += 1
                except Empty:
                    break

            if heart_beat_count == 0:
                _logger.warning(
                    (
                        "WatcherProcess health is no longer responsive. "
                        "%s will be uploaded when closing."
                    ),
                    self.outputs_context.file_type_port_keys,
                )
                # signal the health was degraded and
                # that all the ports should be uploaded when closing
                # the sidecar
                self.outputs_manager.set_all_ports_for_upload()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    loop = get_event_loop()
                    await loop.run_in_executor(executor, self._stop_observer_process)
                    await loop.run_in_executor(executor, self._start_observer_process)

    def _start_observer_process(self) -> None:
        self._event_handler_process.start_process()

    def _stop_observer_process(self) -> None:
        self._event_handler_process.shutdown()

    async def start(self) -> None:
        with log_context(
            _logger, logging.INFO, f"{EventHandlerObserver.__name__} start"
        ):
            self._keep_running = True
            self._task_health_worker = create_task(
                self._health_worker(), name="observer_monitor_health_worker"
            )
            self._start_observer_process()

    async def stop(self) -> None:
        with log_context(
            _logger, logging.INFO, f"{EventHandlerObserver.__name__} stop"
        ):
            self._stop_observer_process()
            self._keep_running = False
            if self._task_health_worker is not None:
                self._task_health_worker.cancel()
                with suppress(CancelledError):
                    await self._task_health_worker
