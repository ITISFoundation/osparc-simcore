import logging
import operator
import os
from abc import ABC, abstractmethod
from functools import reduce

from servicelib.logging_utils import log_catch
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT, BaseObserver
from watchdog.observers.inotify import InotifyEmitter
from watchdog.observers.inotify_buffer import InotifyBuffer
from watchdog.observers.inotify_c import Inotify, InotifyConstants
from watchdog.utils import BaseThread
from watchdog.utils.delayed_queue import DelayedQueue

_EVENTS_TO_WATCH = reduce(
    operator.or_,
    [
        InotifyConstants.IN_MODIFY,
        InotifyConstants.IN_MOVED_FROM,
        InotifyConstants.IN_MOVED_TO,
        InotifyConstants.IN_CREATE,
        InotifyConstants.IN_DELETE,
        InotifyConstants.IN_DELETE_SELF,
        InotifyConstants.IN_DONT_FOLLOW,
        InotifyConstants.IN_CLOSE_WRITE,
    ],
)

logger = logging.getLogger(__name__)


class _ExtendedInotifyBuffer(InotifyBuffer):
    def __init__(
        self, path: bytes, *, recursive: bool = False
    ):  # pylint:disable=super-init-not-called
        # below call to `BaseThread.__init__` is correct since we want to
        # overwrite the `InotifyBuffer.__init__` method
        BaseThread.__init__(self)  # pylint:disable=non-parent-init-called
        self._queue = DelayedQueue(self.delay)
        self._inotify = Inotify(  # pylint:disable=too-many-function-args
            path, recursive=recursive, event_mask=_EVENTS_TO_WATCH
        )
        self.start()


class _ExtendedInotifyEmitter(InotifyEmitter):
    def on_thread_start(self):
        path = os.fsencode(self.watch.path)
        # pylint:disable=attribute-defined-outside-init
        self._inotify = _ExtendedInotifyBuffer(path, recursive=self.watch.is_recursive)


class ExtendedInotifyObserver(BaseObserver):
    """
    Observer thread that schedules watching directories and dispatches
    calls to event handlers.

    Extended to ignore some events which were undesired
    such as attribute changes (permissions, ownership, etc..).
    """

    def __init__(self):
        BaseObserver.__init__(
            self,
            emitter_class=_ExtendedInotifyEmitter,
            timeout=DEFAULT_OBSERVER_TIMEOUT,
        )


class SafeFileSystemEventHandler(ABC, FileSystemEventHandler):
    """
    If an error is raised by `on_any_event` watchdog will stop
    working, no further events will be emitted.
    """

    @abstractmethod
    def event_handler(self, event: FileSystemEvent) -> None:
        """
        User code for handling the event.
        If this raises an error it will not stop future events.
        """

    def on_any_event(self, event: FileSystemEvent) -> None:
        """overwrite and use `event_handler`"""
        super().on_any_event(event)

        # NOTE: if an exception is raised by this handler
        # which is running in the context of the
        # ExtendedInotifyObserver will cause the
        # observer to stop working.
        with log_catch(logger, reraise=False):
            self.event_handler(event)
