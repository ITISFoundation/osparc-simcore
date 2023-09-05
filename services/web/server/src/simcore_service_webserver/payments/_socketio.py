from datetime import datetime

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from models_library.wallets import WalletID

from ..socketio.messages import (
    SOCKET_IO_PAYMENT_COMPLETED_EVENT,
    SocketMessageDict,
    send_messages,
)


async def notify_payment_completed(
    app: web.Application,
    *,
    user_id: UserID,
    payment_id: IDStr,
    wallet_id: WalletID,
    completed_at: datetime,
    completed_success: bool,
    completed_message: str | None
):
    messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_PAYMENT_COMPLETED_EVENT,
            "data": jsonable_encoder(
                {
                    "paymentId": payment_id,
                    "walletId": wallet_id,
                    "completedAt": completed_at,
                    "success": completed_success,
                    "message": completed_message,
                }
            ),
        }
    ]
    await send_messages(app, user_id, messages)
