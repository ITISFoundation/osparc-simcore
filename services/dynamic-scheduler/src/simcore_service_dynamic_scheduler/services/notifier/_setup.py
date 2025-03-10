from servicelib.fastapi.lifespan_utils import LifespanGenerator

from . import _notifier, _socketio


def get_lifespans_notifier() -> list[LifespanGenerator]:
    return [_socketio.lifespan, _notifier.lifespan]
