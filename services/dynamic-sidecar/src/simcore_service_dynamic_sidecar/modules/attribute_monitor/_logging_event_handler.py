import logging
import logging.handlers
import multiprocessing
import stat
from asyncio import CancelledError, Task, create_task, get_event_loop, to_thread
from asyncio import sleep as async_sleep
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from multiprocessing.queues import Queue
from multiprocessing.synchronize import Event
from pathlib import Path
from queue import Empty
from threading import Lock
from time import sleep as blocking_sleep
from typing import Final

from common_library.async_tools import cancel_wait_task
from pydantic import ByteSize, PositiveFloat
from servicelib.logging_utils import log_context
from watchdog.events import FileSystemEvent

from ..multiprocess_logging import (
    _LogForwardingListener,
    create_log_listener,
    setup_log_forwarding,
)
from ._watchdog_extensions import ExtendedInotifyObserver, SafeFileSystemEventHandler

_HEART_BEAT_MARK: Final = 1

# NOTE: with the `spawn`/`forkserver` start methods the created process has to import
# again all the modules, which takes a while
_PROCESS_STARTUP_TIMEOUT_S: Final[PositiveFloat] = 60

logger = logging.getLogger(__name__)


class _LoggingEventHandler(SafeFileSystemEventHandler):
    def event_handler(self, event: FileSystemEvent) -> None:
        # NOTE: runs in the created process

        file_path = Path(event.src_path.decode() if isinstance(event.src_path, bytes) else event.src_path)
        with suppress(FileNotFoundError):
            file_stat = file_path.stat()
            logger.info(
                "Attribute change to: '%s': permissions=%s uid=%s gid=%s size=%s\nFile stat: %s",
                file_path,
                stat.filemode(file_stat.st_mode),
                file_stat.st_uid,
                file_stat.st_gid,
                ByteSize(file_stat.st_size).human_readable(),
                file_stat,
            )


def _process_worker(
    path_to_observe: Path,
    health_check_queue: Queue[int | None],
    stop_queue: Queue[None],
    log_queue: Queue[logging.LogRecord] | None,
    ready_event: Event,
    heart_beat_interval_s: PositiveFloat,
) -> None:
    # NOTE: module level and only receives pickleable arguments,
    # so that it is compatible with any multiprocessing start method

    if log_queue is not None:
        setup_log_forwarding(log_queue)

    observer = ExtendedInotifyObserver()
    file_system_event_handler = _LoggingEventHandler()
    watch = None

    try:
        watch = observer.schedule(
            event_handler=file_system_event_handler,
            path=f"{path_to_observe.absolute()}",
            recursive=True,
        )
        observer.start()
        ready_event.set()

        while stop_queue.qsize() == 0:
            # NOTE: watchdog handles events internally every 1 second.
            # While doing so it will block this thread briefly.
            # Health check delivery may be delayed.

            health_check_queue.put(_HEART_BEAT_MARK)
            blocking_sleep(heart_beat_interval_s)

    except Exception:  # pylint: disable=broad-except
        logger.exception("Unexpected error")
    finally:
        if watch:
            observer.remove_handler_for_watch(file_system_event_handler, watch)
        observer.stop()

        logger.warning("%s exited", _LoggingEventHandlerProcess.__name__)


class _LoggingEventHandlerProcess:
    def __init__(
        self,
        path_to_observe: Path,
        health_check_queue: Queue[int | None],
        heart_beat_interval_s: PositiveFloat,
        *,
        log_queue: Queue[logging.LogRecord] | None = None,
    ) -> None:
        self.path_to_observe: Path = path_to_observe
        self.health_check_queue: Queue[int | None] = health_check_queue
        self.log_queue: Queue[logging.LogRecord] | None = log_queue
        self.heart_beat_interval_s: PositiveFloat = heart_beat_interval_s

        # This is accessible from the creating process and from
        # the process itself and is used to stop the process.
        self._stop_queue: Queue[None] | None = None

        # signals that the observer inside the process is up and running
        self._ready_event: Event = multiprocessing.Event()

        self._process_lock: Lock = Lock()
        self._process: multiprocessing.Process | None = None

    def start_process(self) -> None:
        with (
            log_context(
                logger,
                logging.DEBUG,
                f"{_LoggingEventHandlerProcess.__name__} start_process",
            ),
            self._process_lock,
        ):
            if self._stop_queue is not None or self._process is not None:
                logger.debug("Process already started, skipping")
                return

            self._ready_event.clear()
            self._stop_queue = multiprocessing.Queue()
            self._process = multiprocessing.Process(
                target=_process_worker,
                args=(
                    self.path_to_observe,
                    self.health_check_queue,
                    self._stop_queue,
                    self.log_queue,
                    self._ready_event,
                    self.heart_beat_interval_s,
                ),
                daemon=True,
            )
            self._process.start()

            # NOTE: blocks until the observer is running, otherwise the health
            # check would consider the process as unresponsive
            if not self._ready_event.wait(timeout=_PROCESS_STARTUP_TIMEOUT_S):
                logger.warning(
                    "%s did not start within %s seconds",
                    _LoggingEventHandlerProcess.__name__,
                    _PROCESS_STARTUP_TIMEOUT_S,
                )

    def _stop_process(self) -> None:
        with (
            log_context(
                logger,
                logging.DEBUG,
                f"{_LoggingEventHandlerProcess.__name__} stop_process",
            ),
            self._process_lock,
        ):
            if self._stop_queue is not None:
                self._stop_queue.put(None)
                self._stop_queue = None

            if self._process:
                # force stop the process
                self._process.kill()
                self._process.join()
                self._process = None

    def shutdown(self) -> None:
        with log_context(logger, logging.DEBUG, f"{_LoggingEventHandlerProcess.__name__} shutdown"):
            self._stop_process()

            # signal queue observers to finish
            self.health_check_queue.put(None)


class LoggingEventHandlerObserver:
    """
    Ensures watchdog is not blocked.
    When blocked, it will restart the process handling the watchdog.
    """

    def __init__(
        self,
        path_to_observe: Path,
        heart_beat_interval_s: PositiveFloat,
        *,
        max_heart_beat_wait_interval_s: PositiveFloat = 10,
    ) -> None:
        self.path_to_observe: Path = path_to_observe
        self._heart_beat_interval_s: PositiveFloat = heart_beat_interval_s
        self.max_heart_beat_wait_interval_s: PositiveFloat = max_heart_beat_wait_interval_s

        self._health_check_queue: Queue[int | None] = multiprocessing.Queue()
        self._log_listener: _LogForwardingListener = create_log_listener()
        self._logging_event_handler_process = _LoggingEventHandlerProcess(
            path_to_observe=self.path_to_observe,
            health_check_queue=self._health_check_queue,
            heart_beat_interval_s=heart_beat_interval_s,
            log_queue=self._log_listener.queue,
        )
        self._keep_running: bool = False
        self._task_health_worker: Task | None = None

    @property
    def heart_beat_interval_s(self) -> PositiveFloat:
        return min(self._heart_beat_interval_s * 100, self.max_heart_beat_wait_interval_s)

    async def _health_worker(self) -> None:
        wait_for = self.heart_beat_interval_s
        while self._keep_running:
            await async_sleep(wait_for)

            heart_beat_count = 0
            while True:
                try:
                    self._health_check_queue.get_nowait()
                    heart_beat_count += 1
                except Empty:
                    break

            if heart_beat_count == 0:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    loop = get_event_loop()
                    await loop.run_in_executor(executor, self._stop_observer_process)
                    await loop.run_in_executor(executor, self._start_observer_process)

    def _start_observer_process(self) -> None:
        self._logging_event_handler_process.start_process()

    def _stop_observer_process(self) -> None:
        self._logging_event_handler_process.shutdown()

    async def start(self) -> None:
        with log_context(logger, logging.INFO, f"{LoggingEventHandlerObserver.__name__} start"):
            self._log_listener.start()
            await to_thread(self._start_observer_process)
            self._keep_running = True
            self._task_health_worker = create_task(self._health_worker(), name="observer_monitor_health_worker")

    async def stop(self) -> None:
        with log_context(logger, logging.INFO, f"{LoggingEventHandlerObserver.__name__} stop"):
            self._keep_running = False
            try:
                if self._task_health_worker is not None:
                    with suppress(CancelledError):
                        await cancel_wait_task(self._task_health_worker)
            finally:
                await to_thread(self._stop_observer_process)
                self._log_listener.stop()
