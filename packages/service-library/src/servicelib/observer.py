"""observer pattern module
Allows loose coupling subject and an observer.

"""

import logging
from collections import defaultdict
from functools import wraps
from typing import Callable

from .utils import logged_gather

log = logging.getLogger(__name__)

_event_registry = defaultdict(list)


def register_observer(func: Callable, event: str):
    if func not in _event_registry[event]:
        log.debug("registering %s to event %s", func, event)
        _event_registry[event].append(func)


def registed_observers_report() -> str:
    return "\n".join(
        f" {event}->{len(funcs)} handles" for event, funcs in _event_registry.items()
    )


def is_observer_on_event(func: Callable, event: str) -> bool:
    #
    # FIXME: with_db/02/conftest.py
    # 'assert _on_user_disconnected in _event_registry["SIGNAL_USER_DISCONNECTED"] ' FAILS
    #  showing '_on_user_disconnected' with different ids!!
    #  This typically happens when somewhere importlib.reload was used.
    #  Since the function is stateless and registstered once, for the moment
    #  we make a weaker
    #
    # return any(func.__name__==f.__name__ for f in _event_registry.get(event, []))

    return any(func == f for f in _event_registry.get(event, []))


async def emit(event: str, *args, **kwargs):
    if not _event_registry[event]:
        return

    coroutines = [observer(*args, **kwargs) for observer in _event_registry[event]]
    # all coroutine called in //
    await logged_gather(*coroutines)


def observe(event: str):
    def _decorator(func: Callable):
        register_observer(func, event)

        @wraps(func)
        def _wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return _wrapped

    return _decorator
