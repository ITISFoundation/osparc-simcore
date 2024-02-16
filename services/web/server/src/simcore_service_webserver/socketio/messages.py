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
    ignore_queue: bool,
    max_concurrency: int = 100,
):
    # NOTE: that we configured message queue (i.e. socketio servers are backed with rabbitMQ)
    # so if `ignore_queue=True` then the server can directly communicate with the
    # client without having to send his message first to rabbitMQ and then back to itself.
    #
    await logged_gather(
        *(
            sio.emit(
                event=message["event_type"],
                data=json_dumps(message["data"]),
                room=room,
                ignore_queue=ignore_queue,
            )
            for message in messages
        ),
        reraise=False,
        log=_logger,
        max_concurrency=max_concurrency,
    )


async def send_messages_to_user(
    app: Application,
    user_id: UserID,
    messages: Sequence[SocketMessageDict],
    *,
    has_direct_connection_to_client: bool = True,
) -> None:
    """
    Keyword Arguments:
        has_direct_connection_to_client -- set to False when this message is delivered from a server that has no direct connection to the client (default: {True})
    """
    sio: AsyncServer = get_socket_server(app)

    await _logged_gather_emit(
        sio,
        room=SocketIORoomStr.from_user_id(user_id),
        messages=messages,
        max_concurrency=100,
        ignore_queue=has_direct_connection_to_client,
    )


async def send_messages_to_group(
    app: Application,
    group_id: GroupID,
    messages: Sequence[SocketMessageDict],
    *,
    has_direct_connection_to_client: bool = True,
) -> None:
    """
    Keyword Arguments:
        has_direct_connection_to_client -- set to False when this message is delivered from a server that has no direct connection to the client (default: {True})
    """
    sio: AsyncServer = get_socket_server(app)

    await _logged_gather_emit(
        sio,
        room=SocketIORoomStr.from_group_id(group_id),
        messages=messages,
        max_concurrency=10,
        ignore_queue=has_direct_connection_to_client,
    )
