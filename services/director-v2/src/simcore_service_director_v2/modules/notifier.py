import contextlib
from collections.abc import AsyncIterator

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi_lifespan_manager import LifespanManager
from models_library.api_schemas_directorv2.notifications import ServiceNoMoreCredits
from models_library.api_schemas_directorv2.socketio import (
    SOCKET_IO_SERVICE_NO_MORE_CREDITS_EVENT,
)
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.fastapi.app_state import SingletonInAppStateMixin


class Notifier(SingletonInAppStateMixin):
    app_state_name: str = "notifier"

    def __init__(self, sio_manager: socketio.AsyncAioPikaManager):
        self._sio_manager = sio_manager

    async def notify_shutdown_no_more_credits(self, user_id: UserID, node_id: NodeID, wallet_id: WalletID) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_SERVICE_NO_MORE_CREDITS_EVENT,
            data=jsonable_encoder(ServiceNoMoreCredits(node_id=node_id, wallet_id=wallet_id)),
            room=SocketIORoomStr.from_user_id(user_id),
        )


async def publish_shutdown_no_more_credits(
    app: FastAPI, *, user_id: UserID, node_id: NodeID, wallet_id: WalletID
) -> None:
    notifier: Notifier = Notifier.get_from_app_state(app)
    await notifier.notify_shutdown_no_more_credits(user_id=user_id, node_id=node_id, wallet_id=wallet_id)


def configure_notifier(app_lifespan: LifespanManager) -> None:
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        assert app.state.external_socketio  # nosec

        notifier = Notifier(
            sio_manager=app.state.external_socketio,
        )
        notifier.set_to_app_state(app)
        assert Notifier.get_from_app_state(app) == notifier  # nosec
        try:
            yield
        finally:
            with contextlib.suppress(AttributeError):
                Notifier.pop_from_app_state(app)

    app_lifespan.add(_lifespan)
