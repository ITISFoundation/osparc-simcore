import asyncio
import logging
import time
from abc import ABC, abstractmethod
from asyncio import Queue, Task, create_task
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Final, Optional

from pydantic import NonNegativeFloat, NonNegativeInt, PositiveFloat, PositiveInt
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from watchdog.events import FileSystemEvent
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT

from ..outputs_manager import OutputsManager
from ._directory_utils import get_dir_size

PortEvent = Optional[tuple[str, FileSystemEvent]]

logger = logging.getLogger(__name__)

_KB: Final[PositiveInt] = 1024
_MB: Final[PositiveInt] = 1024 * _KB
_1_MB: Final[PositiveInt] = _MB
_500_MB: Final[PositiveInt] = 500 * _MB


class BaseDelayPolicy(ABC):
    def get_min_interval(self) -> NonNegativeFloat:  # pylint:disable=no-self-use
        return DEFAULT_OBSERVER_TIMEOUT

    @abstractmethod
    def get_wait_interval(self, dir_size: NonNegativeInt) -> NonNegativeFloat:
        """interval to wait based on directory size"""


class DefaultDelayPolicy(BaseDelayPolicy):
    MIN_WAIT: Final[PositiveFloat] = 1
    MAX_WAIT: Final[PositiveFloat] = 10

    _NORMALIZED_MAX_WAIT: Final[PositiveFloat] = MAX_WAIT - MIN_WAIT

    def get_wait_interval(self, dir_size: NonNegativeInt) -> NonNegativeFloat:
        """
        - 1 second, if size of directory <= 1 megabyte
        - 10 seconds, size of directory > 500 megabytes
        - scales between 1 and 10 linearly with directory size
        """
        if dir_size <= _1_MB:
            return self.MIN_WAIT
        if dir_size >= _500_MB:
            return self.MAX_WAIT

        return self.MIN_WAIT + self._NORMALIZED_MAX_WAIT * dir_size / _500_MB


@dataclass
class TrackedEvent:
    last_detection: NonNegativeFloat
    wait_interval: Optional[NonNegativeFloat] = None


class EventFilter:  # pylint:disable=too-many-instance-attributes
    def __init__(
        self,
        outputs_manager: OutputsManager,
        io_log_redirect_cb: Optional[LogRedirectCB],
        delay_policy: BaseDelayPolicy = DefaultDelayPolicy(),
    ):
        self.outputs_manager = outputs_manager
        self.delay_policy = delay_policy
        self.io_log_redirect_cb = io_log_redirect_cb

        self._events_queue: Queue[PortEvent] = Queue()
        self._upload_events_queue: Queue[Optional[str]] = Queue()
        self._worker_task_event_ingestion: Optional[Task] = None
        self._worker_task_check_events: Optional[Task] = None
        self._worker_task_upload_events: Optional[Task] = None
        self._keep_running: bool = True

        self._port_key_tracked_event: dict[str, TrackedEvent] = {}

    async def _worker_event_ingestion(self) -> None:
        """processes incoming events generated by the watchdog"""
        while True:
            event_tuple: PortEvent = await self._events_queue.get()
            if event_tuple is None:
                break

            # NOTE/TODO: `event` is not used for now, maybe remove it?
            port_key, _ = event_tuple

            if port_key not in self._port_key_tracked_event:
                self._port_key_tracked_event[port_key] = TrackedEvent(
                    last_detection=time.time()
                )
            else:
                self._port_key_tracked_event[port_key].last_detection = time.time()

    def _blocking_worker_check_events(self) -> None:
        repeat_interval = self.delay_policy.get_min_interval() * 0.49
        while self._keep_running:

            # can be iterated while modified
            for port_key in list(self._port_key_tracked_event.keys()):
                tracked_event = self._port_key_tracked_event.get(port_key, None)
                if tracked_event is None:  # can disappear while iterated
                    continue

                current_time = time.time()
                elapsed_since_detection = current_time - tracked_event.last_detection

                # ensure minimum interval has passed
                if elapsed_since_detection < (
                    tracked_event.wait_interval or self.delay_policy.get_min_interval()
                ):
                    continue

                # Set the wait_interval for future events.
                # NOTE: Computing the size of a directory is a relatively difficult task,
                # example: on SSD with 1 million files ~ 2 seconds
                # Size of directory will only be computed if:
                # - event was just added
                # - already waited more than the wait_interval
                if (
                    tracked_event.wait_interval is None
                    or elapsed_since_detection > tracked_event.wait_interval
                ):
                    port_key_dir_path = self.outputs_manager.outputs_path / port_key
                    total_wait_for = self.delay_policy.get_wait_interval(
                        get_dir_size(port_key_dir_path)
                    )
                    tracked_event.wait_interval = total_wait_for

                # could require to wait more since wait_interval was just updated
                elapsed_since_detection = current_time - tracked_event.last_detection
                if elapsed_since_detection < tracked_event.wait_interval:
                    continue

                # event chain has finished, request event to upload port and
                # remove event chain from tracking
                self._upload_events_queue.put_nowait(port_key)
                self._port_key_tracked_event.pop(port_key, None)

            time.sleep(repeat_interval)

    async def _worker_check_events(self) -> None:
        """checks at fixed intervals if it should emit events to upload"""
        with ThreadPoolExecutor(max_workers=1) as pool:
            await asyncio.get_event_loop().run_in_executor(
                pool, self._blocking_worker_check_events
            )

    async def _worker_upload_events(self) -> None:
        """requests an upload for `port_key`"""
        while True:
            port_key: Optional[str] = await self._upload_events_queue.get()
            if port_key is None:
                break

            await self.outputs_manager.upload_after_port_change(
                port_key, self.io_log_redirect_cb
            )

    def enqueue(self, port_key: str, event: FileSystemEvent) -> None:
        self._events_queue.put_nowait((port_key, event))

    async def start(self) -> None:
        self._worker_task_event_ingestion = create_task(
            self._worker_event_ingestion(), name=self._worker_event_ingestion.__name__
        )

        self._keep_running = True
        self._worker_task_check_events = create_task(
            self._worker_check_events(), name=self._worker_check_events.__name__
        )

        self._worker_task_upload_events = create_task(
            self._worker_upload_events(), name=self._worker_check_events.__name__
        )

        logger.info("started event filter")

    async def shutdown(self) -> None:
        await self._events_queue.put(None)
        if self._worker_task_event_ingestion is not None:
            await self._worker_task_event_ingestion

        self._keep_running = False
        if self._worker_task_check_events is not None:
            await self._worker_task_check_events

        await self._upload_events_queue.put(None)
        if self._worker_task_upload_events is not None:
            await self._worker_task_upload_events

        logger.info("stopped event filter")
