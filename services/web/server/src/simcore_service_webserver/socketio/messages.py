"""
This module takes care of sending events to the connected webclient through the socket.io interface
"""

import logging
from collections.abc import Sequence
from typing import Final

from aiohttp.web import Application
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.socketio import SocketMessageDict
from models_library.users import GroupID, UserID
from servicelib.json_serialization import json_dumps
from servicelib.utils import logged_gather
from socketio import AsyncServer

from ._utils import get_socket_server

_logger = logging.getLogger(__name__)


#
# List of socket-io event names
#
SOCKET_IO_EVENT: Final[str] = "event"
SOCKET_IO_HEARTBEAT_EVENT: Final[str] = "set_heartbeat_emit_interval"
SOCKET_IO_LOG_EVENT: Final[str] = "logger"
SOCKET_IO_NODE_PROGRESS_EVENT: Final[str] = "nodeProgress"
SOCKET_IO_NODE_UPDATED_EVENT: Final[str] = "nodeUpdated"
SOCKET_IO_PROJECT_PROGRESS_EVENT: Final[str] = "projectProgress"
SOCKET_IO_PROJECT_UPDATED_EVENT: Final[str] = "projectStateUpdated"
SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT: Final[str] = "walletOsparcCreditsUpdated"


async def _logged_gather_emit(
    sio: AsyncServer,
    *,
    room: SocketIORoomStr,
    messages: Sequence[SocketMessageDict],
    max_concurrency: int = 100,
):
    await logged_gather(
        *(
            sio.emit(
                event=message["event_type"],
                data=json_dumps(message["data"]),
                room=room,
            )
            for message in messages
        ),
        reraise=False,
        log=_logger,
        max_concurrency=max_concurrency,
    )


async def send_messages_to_user(
    app: Application, user_id: UserID, messages: Sequence[SocketMessageDict]
) -> None:
    sio: AsyncServer = get_socket_server(app)

    await _logged_gather_emit(
        sio,
        room=SocketIORoomStr.from_user_id(user_id),
        messages=messages,
        max_concurrency=100,
    )


async def send_messages_to_group(
    app: Application, group_id: GroupID, messages: Sequence[SocketMessageDict]
) -> None:
    sio: AsyncServer = get_socket_server(app)

    await _logged_gather_emit(
        sio,
        room=SocketIORoomStr.from_group_id(group_id),
        messages=messages,
        max_concurrency=10,
    )
