import contextlib
import logging

import socketio
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
    SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT,
)
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID
from servicelib.fastapi.http_client import AppStateMixin
from servicelib.socketio_utils import cleanup_socketio_async_pubsub_manager
from settings_library.rabbit import RabbitSettings

from ..db.payment_users_repo import PaymentsUsersRepo
from .postgres import get_engine
from .rabbitmq import get_rabbitmq_settings

_logger = logging.getLogger(__name__)


class Notifier(AppStateMixin):
    app_state_name: str = "notifier"

    def __init__(
        self, sio_manager: socketio.AsyncAioPikaManager, users_repo: PaymentsUsersRepo
    ):
        self._sio_manager = sio_manager
        self._users_repo = users_repo

    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentTransaction,
    ):
        if payment.completed_at is None:
            raise ValueError("This payment is not complete")

        user_primary_group_id = await self._users_repo.get_primary_group_id(user_id)

        # NOTE: We assume that the user has been added to all
        # rooms associated to his groups
        assert payment.completed_at is not None  # nosec

        return await self._sio_manager.emit(
            SOCKET_IO_PAYMENT_COMPLETED_EVENT,
            data=jsonable_encoder(payment, by_alias=True),
            room=f"{user_primary_group_id}",
        )

    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ):
        user_primary_group_id = await self._users_repo.get_primary_group_id(user_id)

        return await self._sio_manager.emit(
            SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT,
            data=jsonable_encoder(payment_method, by_alias=True),
            room=f"{user_primary_group_id}",
        )


def setup_socketio(app: FastAPI):
    settings: RabbitSettings = get_rabbitmq_settings(app)

    async def _on_startup() -> None:
        assert app.state.rabbitmq_client  # nosec

        # Connect to the as an external process in write-only mode
        # SEE https://python-socketio.readthedocs.io/en/stable/server.html#emitting-from-external-processes
        app.state.external_socketio = socketio.AsyncAioPikaManager(
            url=settings.dsn, logger=_logger, write_only=True
        )

        notifier = Notifier(
            sio_manager=app.state.external_socketio,
            users_repo=PaymentsUsersRepo(get_engine(app)),
        )
        notifier.set_to_app_state(app)
        assert Notifier.get_from_app_state(app) == notifier  # nosec

    async def _on_shutdown() -> None:

        if app.state.external_socketio:
            await cleanup_socketio_async_pubsub_manager(
                server_manager=app.state.external_socketio
            )

        with contextlib.suppress(AttributeError):
            Notifier.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
