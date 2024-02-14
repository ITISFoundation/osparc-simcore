import logging

import socketio
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
    SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID

from ..db.payment_users_repo import PaymentsUsersRepo
from .notifier_abc import NotificationProvider

_logger = logging.getLogger(__name__)


class WebSocketProvider(NotificationProvider):
    def __init__(
        self, sio_manager: socketio.AsyncAioPikaManager, users_repo: PaymentsUsersRepo
    ):
        self._sio_manager = sio_manager
        self._users_repo = users_repo

    async def on_startup(self):
        ...

    async def on_shutdown(self):
        ...

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
            room=SocketIORoomStr.from_group_id(user_primary_group_id),
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
            room=SocketIORoomStr.from_group_id(user_primary_group_id),
        )
