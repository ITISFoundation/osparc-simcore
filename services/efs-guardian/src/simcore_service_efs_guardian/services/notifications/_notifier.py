import contextlib
from typing import Final

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import BaseModel, ByteSize, Field
from servicelib.fastapi.app_state import SingletonInAppStateMixin

SOCKET_IO_EFS_DISK_USAGE_EVENT: Final[str] = "efsNodeDiskUsage"


class EfsNodeDiskUsage(BaseModel):
    node_id: NodeID
    used: ByteSize = Field(description="used space")
    free: ByteSize = Field(description="remaining space")
    total: ByteSize = Field(description="total space = free + used")
    used_percent: float = Field(
        gte=0.00,
        lte=100.00,
        description="Percent of used space relative to the total space",
    )


class Notifier(SingletonInAppStateMixin):
    app_state_name: str = "notifier"

    def __init__(self, sio_manager: socketio.AsyncAioPikaManager):
        self._sio_manager = sio_manager

    async def notify_service_efs_disk_usage(
        self, user_id: UserID, efs_node_disk_usage: EfsNodeDiskUsage
    ) -> None:
        await self._sio_manager.emit(
            SOCKET_IO_EFS_DISK_USAGE_EVENT,
            data=jsonable_encoder(efs_node_disk_usage),
            room=SocketIORoomStr.from_user_id(user_id),
        )


def setup_notifier(app: FastAPI):
    async def _on_startup() -> None:
        assert app.state.external_socketio  # nosec

        notifier = Notifier(
            sio_manager=app.state.external_socketio,
        )
        notifier.set_to_app_state(app)
        assert Notifier.get_from_app_state(app) == notifier  # nosec

    async def _on_shutdown() -> None:
        with contextlib.suppress(AttributeError):
            Notifier.pop_from_app_state(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)
