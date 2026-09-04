import logging
import multiprocessing
import stat
from asyncio import CancelledError, Task, create_task, get_event_loop
from asyncio import sleep as async_sleep
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from multiprocessing.queues import Queue
from pathlib import Path
from queue import Empty
from time import sleep as blocking_sleep
from typing import Final

from pydantic import ByteSize, PositiveFloat
from servicelib.logging_utils import log_context
from watchdog.events import FileSystemEvent

from ._watchdog_extensions import ExtendedInotifyObserver, SafeFileSystemEventHandler

_HEART_BEAT_MARK: Final = 1

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
    heart_beat_interval_s: PositiveFloat,
) -> None:
    # NOTE: module level and only receives pickleable arguments,
    # so that it is compatible with any multiprocessing start method

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
    ) -> None:
        self.path_to_observe: Path = path_to_observe
        self.health_check_queue: Queue[int | None] = health_check_queue
        self.heart_beat_interval_s: PositiveFloat = heart_beat_interval_s

        # This is accessible from the creating process and from
        # the process itself and is used to stop the process.
        self._stop_queue: Queue[None] = multiprocessing.Queue()

        self._process: multiprocessing.Process | None = None

    def start_process(self) -> None:
        with log_context(
            logger,
            logging.DEBUG,
            f"{_LoggingEventHandlerProcess.__name__} start_process",
        ):
            self._process = multiprocessing.Process(
                target=_process_worker,
                args=(
                    self.path_to_observe,
                    self.health_check_queue,
                    self._stop_queue,
                    self.heart_beat_interval_s,
                ),
                daemon=True,
            )
            self._process.start()

    def _stop_process(self) -> None:
        with log_context(
            logger,
            logging.DEBUG,
            f"{_LoggingEventHandlerProcess.__name__} stop_process",
        ):
            self._stop_queue.put(None)

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
        self._logging_event_handler_process = _LoggingEventHandlerProcess(
            path_to_observe=self.path_to_observe,
            health_check_queue=self._health_check_queue,
            heart_beat_interval_s=heart_beat_interval_s,
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
            self._keep_running = True
            self._task_health_worker = create_task(self._health_worker(), name="observer_monitor_health_worker")
            self._start_observer_process()

    async def stop(self) -> None:
        with log_context(logger, logging.INFO, f"{LoggingEventHandlerObserver.__name__} stop"):
            self._stop_observer_process()
            self._keep_running = False
            if self._task_health_worker is not None:
                self._task_health_worker.cancel("stopping health worker")
                with suppress(CancelledError):
                    await self._task_health_worker
