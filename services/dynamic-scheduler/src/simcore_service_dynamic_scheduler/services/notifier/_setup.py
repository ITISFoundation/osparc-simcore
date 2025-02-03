from servicelib.fastapi.lifespan_utils import SetupGenerator

from . import _notifier, _socketio


def get_notifier_lifespans() -> list[SetupGenerator]:
    return [_socketio.lifespan, _notifier.lifespan]
