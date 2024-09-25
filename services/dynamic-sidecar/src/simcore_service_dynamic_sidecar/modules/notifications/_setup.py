import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from ..notifications._notifier import setup_notifier
from ..notifications._socketio import setup_socketio

_logger = logging.getLogger(__name__)


def setup_notifications(app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, "setup notifications"):
        setup_socketio(app)
        setup_notifier(app)
