import contextlib
import logging
from pathlib import Path

import socketio
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_dynamic_sidecar.socketio import (
    SOCKET_IO_SERVICE_DISK_USAGE_EVENT,
)
from models_library.api_schemas_dynamic_sidecar.telemetry import DiskUsage
from models_library.users import GroupID
from servicelib.fastapi.app_state import SingletonInAppStateMixin

_logger = logging.getLogger(__name__)


class Notifier(SingletonInAppStateMixin):
    app_state_name: str = "notifier"

    def __init__(self, sio_manager: socketio.AsyncAioPikaManager):
        self._sio_manager = sio_manager

    async def notify_service_disk_usage(
        self, primary_group_id: GroupID, usage: dict[Path, DiskUsage]
    ) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_SERVICE_DISK_USAGE_EVENT,
            data=jsonable_encoder(usage),
            room=f"{primary_group_id}",
        )


async def publish_disk_usage(
    app: FastAPI, *, primary_group_id: GroupID, usage: dict[Path, DiskUsage]
) -> None:
    notifier: Notifier = Notifier.get_from_app_state(app)
    await notifier.notify_service_disk_usage(
        primary_group_id=primary_group_id, usage=usage
    )


def setup_notifier(app: FastAPI):
    async def _on_startup() -> None:
        assert app.state.external_socketio  # nosec

        notifier = Notifier(
            sio_manager=app.state.external_socketio,
        )
        notifier.set_to_app_state(app)
        assert Notifier.get_from_app_state(app) == notifier  # nosec

    async def _on_shutdown() -> None:
        with contextlib.suppress(AttributeError):
            Notifier.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
