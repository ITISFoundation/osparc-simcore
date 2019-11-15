import asyncio
import logging
from collections import defaultdict
from functools import wraps

from .types import SignalType

log = logging.getLogger(__name__)

event_registry = defaultdict(list)

async def emit(event: SignalType, *args, **kwargs):
    if not event_registry[event]:
        return

    coroutines = [observer(*args, **kwargs) for observer in event_registry[event]]
    # all coroutine called in //
    await asyncio.gather(*coroutines, return_exceptions=True)

def observe(event: SignalType):
    def decorator(func):
        if func not in event_registry[event]:
            log.debug("registering %s to event %s", func, event)
            event_registry[event].append(func)

        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped
    return decorator


__all__ = (
    'SignalType'
    'observe'
    'emit'
)
