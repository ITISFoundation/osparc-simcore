import logging
from asyncio import Queue as AsyncioQueue
from asyncio import Task, create_task, get_event_loop
from asyncio import sleep as async_sleep
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Queue
from pathlib import Path
from queue import Empty
from time import sleep as blocking_sleep
from typing import Final, Optional

from pydantic import PositiveFloat
from servicelib.logging_utils import log_context
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from ._watchdog_extentions import ExtendedInotifyObserver

_HEART_BEAT_MARK: Final = 1

logger = logging.getLogger(__name__)


class _OutputsEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        path_to_observe: Path,
        outputs_port_keys: set[str],
        events_queue: Queue,
    ):
        super().__init__()

        self.path_to_observe: Path = path_to_observe
        self.outputs_port_keys: set[str] = outputs_port_keys
        self.events_queue: Queue = events_queue

    def on_any_event(self, event: FileSystemEvent) -> None:
        super().on_any_event(event)

        # NOTE: filtering out all events which are not relative to modifying
        # the contents of the `port_key` folders from the outputs directory

        path_relative_to_outputs = Path(event.src_path).relative_to(
            self.path_to_observe
        )

        # discard event if not part of a subfolder
        relative_path_parents = path_relative_to_outputs.parents
        event_in_subdirs = len(relative_path_parents) > 0
        if not event_in_subdirs:
            return

        # only accept events generated inside `port_key` subfolder
        port_key_candidate = f"{relative_path_parents[0]}"
        if port_key_candidate in self.outputs_port_keys:
            self.events_queue.put_nowait(port_key_candidate)


class _ObserverProcess(Process):
    """
    The ExtendedInotifyObserver is a bit flaky,
    sometimes it causes the process to lock.
    This process is designed to be killed and restarted.
    """

    def __init__(
        self,
        path_to_observe: Path,
        outputs_port_keys: set[str],
        events_queue: Queue,
        health_check_queue: Queue,
        heart_beat_interval_s: PositiveFloat,
    ) -> None:
        self.path_to_observe: Path = path_to_observe
        self.outputs_port_keys: set[str] = outputs_port_keys
        self.events_queue: Queue = events_queue
        self.health_check_queue: Queue = health_check_queue
        self.heart_beat_interval_s: PositiveFloat = heart_beat_interval_s

        # This is accessible from the creating process and from
        # the process itself
        self._internal_queue: Queue = Queue()

        super().__init__(daemon=True)

    def run(self) -> None:
        try:
            observer = ExtendedInotifyObserver()

            outputs_event_handler = _OutputsEventHandler(
                path_to_observe=self.path_to_observe,
                outputs_port_keys=self.outputs_port_keys,
                events_queue=self.events_queue,
            )
            observer.schedule(
                event_handler=outputs_event_handler,
                path=f"{self.path_to_observe.absolute()}",
                recursive=True,
            )
            observer.start()

            while self._internal_queue.qsize() == 0:
                # watchdog internally uses 1 sec interval to detect events
                # sleeping for less is useless.
                # If this value is bigger then the DEFAULT_OBSERVER_TIMEOUT
                # the result will not be as expected. Keep sleep to 1 second

                # NOTE: watchdog will block this thread for some period of
                # time while handling inotify events
                # the health_check sending could be delayed

                self.health_check_queue.put_nowait(_HEART_BEAT_MARK)
                blocking_sleep(self.heart_beat_interval_s)

        except Exception:  # pylint: disable=broad-except
            logger.exception("Watchers failed upon initialization")
        finally:
            observer.stop()
            observer.join()

            # signal queue observers to finish
            self.events_queue.put(None)
            self.health_check_queue.put(None)

    def stop(self) -> None:
        self._internal_queue.put(None)


class ObserverMonitor:  # pylint: disable=too-many-instance-attributes
    """
    Ensures the ObserverProcess is not blocked.
    When blocked, it will be restarted.
    """

    def __init__(
        self,
        path_to_observe: Path,
        outputs_port_keys: set[str],
        health_queue: AsyncioQueue,
        events_queue: Queue,
        heart_beat_interval_s: PositiveFloat,
        max_heart_beat_wait_interval_s: PositiveFloat = 10,
    ) -> None:

        self.path_to_observe: Path = path_to_observe
        self.outputs_port_keys: set[str] = outputs_port_keys
        self.health_queue: AsyncioQueue = health_queue
        self.events_queue: Queue = events_queue
        self.heart_beat_interval_s: PositiveFloat = heart_beat_interval_s
        self.max_heart_beat_wait_interval_s: PositiveFloat = (
            max_heart_beat_wait_interval_s
        )

        self._health_check_queue: Queue = Queue()
        self._task_health_worker: Optional[Task] = None
        self._observer_process: Optional[_ObserverProcess] = None
        self._keep_running: bool = False

    def _start_observer_process(self) -> None:
        self._observer_process = _ObserverProcess(
            path_to_observe=self.path_to_observe,
            outputs_port_keys=self.outputs_port_keys,
            events_queue=self.events_queue,
            health_check_queue=self._health_check_queue,
            heart_beat_interval_s=self.heart_beat_interval_s,
        )
        self._observer_process.start()

    def _stop_observer_process(self, force: bool = False) -> None:
        """force is True, the process will be killed"""

        if self._observer_process is None:
            return

        if force:
            self._observer_process.kill()
            self._observer_process.join()
        else:
            self._observer_process.stop()
            self._observer_process.join()

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
                    self._health_check_queue.get_nowait()
                    heart_beat_count += 1
                except Empty:
                    break

            if heart_beat_count == 0:
                logger.warning(
                    (
                        "WatcherProcess health is no longer responsive. "
                        "%s will be uploaded when closing."
                    ),
                    self.outputs_port_keys,
                )
                # signal the health was degraded and
                # that all the ports should be uploaded when closing
                # the sidecar
                await self.health_queue.put(1)

                with ThreadPoolExecutor(max_workers=1) as executor:
                    loop = get_event_loop()
                    await loop.run_in_executor(
                        executor, self._stop_observer_process, True
                    )
                    await loop.run_in_executor(executor, self._start_observer_process)

    async def start(self) -> None:
        self._keep_running = True
        self._task_health_worker = create_task(
            self._health_worker(), name="observer_monitor_health_worker"
        )
        self._start_observer_process()
        logger.info("started observer monitor")

    async def stop(self) -> None:
        with log_context(logger, logging.INFO, f"{ObserverMonitor.__name__} shutdown"):
            if self._task_health_worker is not None:
                self._keep_running = False
                await self._task_health_worker
