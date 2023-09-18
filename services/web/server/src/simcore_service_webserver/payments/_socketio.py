from aiohttp import web
from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder

from ..socketio.messages import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
    SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT,
    SocketMessageDict,
    send_messages,
)


async def notify_payment_completed(
    app: web.Application,
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


async def notify_payment_method_acked(
    app: web.Application,
    *,
    user_id: UserID,
    payment_method_transaction: PaymentMethodTransaction,
):
    messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_PAYMENT_METHOD_ACKED_EVENT,
            "data": jsonable_encoder(payment_method_transaction, by_alias=True),
        }
    ]
    await send_messages(app, user_id, messages)
