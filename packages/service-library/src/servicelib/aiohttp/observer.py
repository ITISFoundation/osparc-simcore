"""observer pattern module

Allows loose coupling subject and an observer.
"""

import logging
from collections import defaultdict
from collections.abc import Callable

from aiohttp import web

from ..utils import logged_gather

log = logging.getLogger(__name__)


_APP_OBSERVER_EVENTS_REGISTRY_KEY = "{__name__}.event_registry"


class ObserverRegistryNotFoundError(RuntimeError):
    ...


def setup_observer_registry(app: web.Application):
    # only once
    app.setdefault(_APP_OBSERVER_EVENTS_REGISTRY_KEY, defaultdict(list))


def _get_registry(app: web.Application) -> defaultdict:
    try:
        registry: defaultdict = app[_APP_OBSERVER_EVENTS_REGISTRY_KEY]
        return registry
    except KeyError as err:
        msg = "Could not find observer registry. TIP: initialize app with setup_observer_registry"
        raise ObserverRegistryNotFoundError(msg) from err


def register_observer(app: web.Application, func: Callable, event: str):
    _event_registry = _get_registry(app)

    if func not in _event_registry[event]:
        log.debug("registering %s to event %s", func, event)
        _event_registry[event].append(func)


def registed_observers_report(app: web.Application) -> str:
    if _event_registry := app.get(_APP_OBSERVER_EVENTS_REGISTRY_KEY):
        return "\n".join(
            f" {event}->{len(funcs)} handles"
            for event, funcs in _event_registry.items()
        )
    return "No observers registry found in app"


async def emit(app: web.Application, event: str, *args, **kwargs):
    _event_registry = _get_registry(app)
    if not _event_registry[event]:
        return

    coroutines = [observer(*args, **kwargs) for observer in _event_registry[event]]
    # all coroutine called in //
    await logged_gather(*coroutines)
