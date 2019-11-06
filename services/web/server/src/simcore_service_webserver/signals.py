import logging

log = logging.getLogger(__name__)


OBSERVERS = list()

def subscribe(callable):
    if not callable in OBSERVERS:
        OBSERVERS.append(callable)

def unsubscribe(callable):
    if callable in OBSERVERS:
        OBSERVERS.remove(callable)

async def user_disconnected_event(user_id: str) -> None:
    log.warning("I am disconnected and my id is %s", user_id)
    for observer in OBSERVERS:
        observer(user_id)
