import os
from functools import reduce

from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT, BaseObserver
from watchdog.observers.inotify import InotifyBuffer, InotifyEmitter
from watchdog.observers.inotify_c import Inotify, InotifyConstants
from watchdog.utils import BaseThread
from watchdog.utils.delayed_queue import DelayedQueue

_EVENTS_TO_WATCH = reduce(
    lambda x, y: x | y,
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


class _ExtendedInotifyBuffer(InotifyBuffer):
    def __init__(self, path, recursive=False):  # pylint:disable=super-init-not-called
        BaseThread.__init__(self)  # pylint:disable=non-parent-init-called
        self._queue = DelayedQueue(self.delay)
        self._inotify = Inotify(path, recursive, _EVENTS_TO_WATCH)
        self.start()


class _ExtendedInotifyEmitter(InotifyEmitter):
    def on_thread_start(self):
        path = os.fsencode(self.watch.path)
        # pylint:disable=attribute-defined-outside-init
        self._inotify = _ExtendedInotifyBuffer(path, self.watch.is_recursive)


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
