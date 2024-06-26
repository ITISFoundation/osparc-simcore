from fastapi import FastAPI

from . import _notifier, _socketio


def setup_notifier(app: FastAPI):
    _socketio.setup(app)
    _notifier.setup_notifier(app)
