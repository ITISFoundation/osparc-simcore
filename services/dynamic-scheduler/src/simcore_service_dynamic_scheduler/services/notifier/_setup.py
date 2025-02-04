from servicelib.fastapi.lifespan_utils import LifespanGenerator

from . import _notifier, _socketio


def get_notifier_lifespans() -> list[LifespanGenerator]:
    return [_socketio.lifespan, _notifier.lifespan]
