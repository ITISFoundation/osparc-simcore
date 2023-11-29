import logging

import socketio
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
)
from models_library.api_schemas_webserver.wallets import PaymentTransaction
from models_library.users import GroupID
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings

from .rabbitmq import get_rabbitmq_settings

_logger = logging.getLogger(__name__)


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

    async def _on_shutdown() -> None:
        if app.state.external_socketio:
            await cleanup_socketio_async_pubsub_manager(
                server_manager=app.state.external_socketio
            )

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


async def notify_payment_completed(
    app: FastAPI,
    *,
    user_primary_group_id: GroupID,
    payment: PaymentTransaction,
):
    # NOTE: We assume that the user has been added to all
    # rooms associated to his groups
    assert payment.completed_at is not None  # nosec

    external_socketio: socketio.AsyncAioPikaManager = app.state.external_socketio

    return await external_socketio.emit(
        SOCKET_IO_PAYMENT_COMPLETED_EVENT,
        data=jsonable_encoder(payment, by_alias=True),
        room=f"{user_primary_group_id}",
    )
