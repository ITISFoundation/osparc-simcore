import logging
from dataclasses import dataclass

import socketio
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_notifiers.socketio import (
    SOCKET_IO_NOTIFIER_COMPLETED_EVENT,
    SOCKET_IO_NOTIFIER_METHOD_ACKED_EVENT,
)
from models_library.users import GroupID
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings

from .rabbitmq import get_rabbitmq_settings

_logger = logging.getLogger(__name__)


@dataclass
class SocketIoNotifier:
    _sio_manager: socketio.AsyncAioPikaManager

    async def notify_notifier_completed(
        self,
        user_primary_group_id: GroupID,
        notifier: NotifierTransaction,
    ):
        # NOTE: We assume that the user has been added to all
        # rooms associated to his groups
        assert notifier.completed_at is not None  # nosec

        return await self._sio_manager.emit(
            SOCKET_IO_NOTIFIER_COMPLETED_EVENT,
            data=jsonable_encoder(notifier, by_alias=True),
            room=f"{user_primary_group_id}",
        )

    async def notify_notifier_method_acked(
        self,
        user_primary_group_id: GroupID,
        notifier_method: NotifierMethodTransaction,
    ):
        return await self._sio_manager.emit(
            SOCKET_IO_NOTIFIER_METHOD_ACKED_EVENT,
            data=jsonable_encoder(notifier_method, by_alias=True),
            room=f"{user_primary_group_id}",
        )


def setup_socketio(app: FastAPI):
    settings: RabbitSettings = get_rabbitmq_settings(app)

    async def _on_startup() -> None:
        assert app.state.rabbitmq_client  # nosec

        #
        # https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
        #
        # Connect to the as an external process in write-only mode
        #
        app.state.external_socketio = socketio.AsyncAioPikaManager(
            url=settings.dsn, logger=_logger, write_only=True
        )

        # NOTE: this might be moved somewhere else when notifier incorporates emails etc
        app.state.notifier = SocketIoNotifier(_sio_manager=app.state.external_socketio)

    async def _on_shutdown() -> None:
        if app.state.external_socketio:
            await cleanup_socketio_async_pubsub_manager(
                server_manager=app.state.external_socketio
            )

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


async def notify_notifier_completed(
    app: FastAPI,
    *,
    user_primary_group_id: GroupID,
):

    notifier: SocketIoNotifier = app.state.notifier

    return await notifier.notify_notifier_completed(
        user_primary_group_id=user_primary_group_id, notifier=notifier
    )
