"""observer pattern module
Allows loose coupling subject and an observer.

"""

import logging
from collections import defaultdict
from functools import wraps

from .utils import logged_gather

log = logging.getLogger(__name__)

event_registry = defaultdict(list)


async def emit(event: str, *args, **kwargs):
    if not event_registry[event]:
        return

    coroutines = [observer(*args, **kwargs) for observer in event_registry[event]]
    # all coroutine called in //
    await logged_gather(*coroutines)


def observe(event: str):
    def decorator(func):
        if func not in event_registry[event]:
            log.debug("registering %s to event %s", func, event)
            event_registry[event].append(func)

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapped

    return decorator
