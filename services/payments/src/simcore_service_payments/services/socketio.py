import logging
from collections.abc import Sequence

import socketio
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
)
from models_library.api_schemas_webserver.wallets import PaymentTransaction
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from servicelib.json_serialization import json_dumps
from servicelib.utils import logged_gather
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
        app.state.external_sio = socketio.AsyncAioPikaManager(
            url=settings.dsn, logger=_logger, write_only=True
        )

    async def _on_shutdown() -> None:
        ...

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)


async def emit_to_frontend(
    app: FastAPI, event_name: str, data: dict, to: str | None = None
):

    # Send messages to clients from external processes, such as Celery workers or auxiliary scripts.
    return await app.state.external_sio.emit(event_name, data=data, to=to)


async def notify_payment_completed(
    app: FastAPI,
    *,
    user_id: UserID,
    payment: PaymentTransaction,
):
    assert payment.completed_at is not None  # nosec

    messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_PAYMENT_COMPLETED_EVENT,
            "data": jsonable_encoder(payment, by_alias=True),
        }
    ]
    await send_messages(app, user_id, messages)


async def send_messages(
    app: FastAPI, user_id: UserID, messages: Sequence[SocketMessageDict]
) -> None:

    sio = app.state.external_sio

    socket_ids: list[str] = []
    # with managed_resource(user_id, None, app) as user_session:
    #     socket_ids = await user_session.find_socket_ids()

    await logged_gather(
        *(
            sio.emit(message["event_type"], data=json_dumps(message["data"]), room=sid)
            for message in messages
            for sid in socket_ids
        ),
        reraise=False,
        log=_logger,
        max_concurrency=100,
    )
