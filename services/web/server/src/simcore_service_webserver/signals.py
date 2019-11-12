import logging

from aiohttp import web

log = logging.getLogger(__name__)

OBSERVERS = []

def subscribe(observer):
    if not observer in OBSERVERS:
        log.debug("subscribing observer %s", observer)
        OBSERVERS.append(observer)

def unsubscribe(observer):
    if observer in OBSERVERS:
        log.debug("unsubscribing observer %s", observer)
        OBSERVERS.remove(observer)

async def user_disconnected_event(request: web.Request) -> None:
    log.warning("I am disconnected through request %s", request)
    for observer in OBSERVERS:
        observer.notify(request)
