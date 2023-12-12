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
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ..db.payment_users_repo import PaymentsUsersRepo
from .postgres import get_engine

_logger = logging.getLogger(__name__)


class Notifier(SingletonInAppStateMixin):
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
            msg = "Incomplete payment"
            raise ValueError(msg)

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


def setup_notifier(app: FastAPI):
    async def _on_startup() -> None:
        assert app.state.external_socketio  # nosec

        notifier = Notifier(
            sio_manager=app.state.external_socketio,
            users_repo=PaymentsUsersRepo(get_engine(app)),
        )
        notifier.set_to_app_state(app)
        assert Notifier.get_from_app_state(app) == notifier  # nosec

    async def _on_shutdown() -> None:

        with contextlib.suppress(AttributeError):
            Notifier.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
