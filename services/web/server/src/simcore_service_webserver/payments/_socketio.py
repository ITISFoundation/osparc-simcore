from aiohttp import web
from models_library.api_schemas_payments.socketio import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
    SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT,
)
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder

from ..socketio.messages import send_message_to_user


async def notify_payment_completed(
    app: web.Application,
    *,
    user_id: UserID,
    payment: PaymentTransaction,
):
    assert payment.completed_at is not None  # nosec

    await send_message_to_user(
        app,
        user_id,
        message=SocketMessageDict(
            event_type=SOCKET_IO_PAYMENT_COMPLETED_EVENT,
            data=jsonable_encoder(payment, by_alias=True),
        ),
    )


async def notify_payment_method_acked(
    app: web.Application,
    *,
    user_id: UserID,
    payment_method_transaction: PaymentMethodTransaction,
):
    await send_message_to_user(
        app,
        user_id,
        message=SocketMessageDict(
            event_type=SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT,
            data=jsonable_encoder(payment_method_transaction, by_alias=True),
        ),
    )
