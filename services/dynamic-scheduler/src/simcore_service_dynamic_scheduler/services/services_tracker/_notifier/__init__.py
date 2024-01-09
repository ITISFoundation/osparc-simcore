from fastapi import FastAPI

from ._core import publish_message, setup_core
from ._socketio import setup_socketio


def setup_notifier(app: FastAPI) -> None:
    setup_socketio(app)
    setup_core(app)


__all__: tuple[str, ...] = ("publish_message", "setup_notifier")
