from aiohttp import web
from models_library.basic_types import IDStr
from models_library.users import UserID
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
    error: str | None
):
    messages: list[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_PAYMENT_COMPLETED_EVENT,
            "data": {"payment_id": payment_id, "wallet_id": wallet_id, "error": error},
        }
    ]
    await send_messages(app, user_id, messages)
