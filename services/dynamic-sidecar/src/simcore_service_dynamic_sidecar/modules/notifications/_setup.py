import logging

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.logging_utils import log_context

from ..notifications._notifier import configure_notifier
from ..notifications._socketio import configure_socketio

_logger = logging.getLogger(__name__)


def configure_notifications(app_lifespan: LifespanManager[FastAPI]) -> None:
    with log_context(_logger, logging.INFO, "setup notifications"):
        configure_socketio(app_lifespan)
        configure_notifier(app_lifespan)
