"""
This module takes care of sending events to the connected webclient through the socket.io interface
"""

import logging
from typing import Final

from aiohttp.web import Application
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.socketio import SocketMessageDict
from models_library.users import GroupID, UserID
from servicelib.json_serialization import json_dumps
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


async def _safe_emit(
    sio: AsyncServer,
    *,
    room: SocketIORoomStr,
    message: SocketMessageDict,
    ignore_queue: bool,
):
    # NOTE 1 : we configured message queue (i.e. socketio servers are backed with rabbitMQ)
    # so if `ignore_queue=True` then the server can directly communicate with the
    # client without having to send his message first to rabbitMQ and then back to itself.
    #
    # NOTE 2: `emit` method is not designed to be used concurrently
    try:
        event = message["event_type"]
        data = json_dumps(message["data"])
        await sio.emit(
            event=event,
            data=data,
            room=room,
            ignore_queue=ignore_queue,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        _logger.warning(
            "Failed to deliver %s message to %s size=%d",
            f"{event=}",
            f"{room=}",
            len(data),
            exc_info=True,
        )


async def send_messages_to_user(
    app: Application,
    user_id: UserID,
    message: SocketMessageDict,
    *,
    has_direct_connection_to_client: bool = True,
) -> None:
    """
    Keyword Arguments:
        has_direct_connection_to_client -- set to False when this message is delivered from a server that has no direct connection to the client (default: {True})
        An example where this is value is False, is sending messages to a user in the GC

    QUESTION: a user might have different tabs opened or connect with a different browser/computer. Does stickiness
    make all these connection associated to the same server?
    """
    sio: AsyncServer = get_socket_server(app)

    await _safe_emit(
        sio,
        room=SocketIORoomStr.from_user_id(user_id),
        message=message,
        ignore_queue=has_direct_connection_to_client,
    )


async def send_message_to_standard_group(
    app: Application,
    group_id: GroupID,
    message: SocketMessageDict,
) -> None:
    """
    WARNING: please do not use primary groups here. To transmit to the
    user use instead send_messages_to_user

    NOTE: despite the name, it can also be used for EVERYONE
    """
    sio: AsyncServer = get_socket_server(app)

    await _safe_emit(
        sio,
        room=SocketIORoomStr.from_group_id(group_id),
        message=message,
        ignore_queue=False,
        # NOTE: A standard group refers to different users
        # that might be connected to different replicas
    )
