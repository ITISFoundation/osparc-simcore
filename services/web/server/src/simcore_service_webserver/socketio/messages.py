"""
This module takes care of sending events to the connected webclient through the socket.io interface
"""

import logging
from typing import Final

from aiohttp.web import Application
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from servicelib.logging_utils import log_catch
from socketio import AsyncServer  # type: ignore[import-untyped]

from ._utils import get_socket_server

_logger = logging.getLogger(__name__)


#
# List of socket-io event names
#
SOCKET_IO_EVENT: Final[str] = "event"
SOCKET_IO_HEARTBEAT_EVENT: Final[str] = "set_heartbeat_emit_interval"
SOCKET_IO_LOG_EVENT: Final[str] = "logger"

SOCKET_IO_NODE_UPDATED_EVENT: Final[str] = "nodeUpdated"

SOCKET_IO_PROJECT_UPDATED_EVENT: Final[str] = "projectStateUpdated"
# SOCKET_IO_PROJECT_STORE_UPDATED_EVENT: Final[str] = "projectStoreUpdated"

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
    with log_catch(_logger, reraise=False):
        event = message["event_type"]
        data = jsonable_encoder(message["data"])
        await sio.emit(
            event=event,
            data=data,
            room=room,
            ignore_queue=ignore_queue,
        )
        _logger.debug("emitted socketio event '%s' to room '%s'", event, room)


async def send_message_to_user(
    app: Application,
    user_id: UserID,
    message: SocketMessageDict,
    *,
    ignore_queue: bool = False,
) -> None:
    """
    Keyword Arguments:
        ignore_queue -- set to True when this message is delivered from a server that has no direct connection to the user client (default: {False})
        Be careful with this option, as it can lead to message loss if the user is not connected to this server!!
    """
    sio: AsyncServer = get_socket_server(app)

    await _safe_emit(
        sio,
        room=SocketIORoomStr.from_user_id(user_id),
        message=message,
        ignore_queue=ignore_queue,
    )


async def send_message_to_standard_group(
    app: Application,
    group_id: GroupID,
    message: SocketMessageDict,
) -> None:
    """
    WARNING: please do not use primary groups here. To transmit to the
    user use instead send_message_to_user

    NOTE: despite the name, it can also be used for EVERYONE
    """
    sio: AsyncServer = get_socket_server(app)

    await _safe_emit(
        sio,
        room=SocketIORoomStr.from_group_id(group_id),
        message=message,
        # NOTE: A standard group refers to different users
        # that might be connected to different replicas
        ignore_queue=False,
    )


async def send_message_to_project_room(
    app: Application,
    project_id: ProjectID,
    message: SocketMessageDict,
) -> None:
    sio: AsyncServer = get_socket_server(app)

    await _safe_emit(
        sio,
        room=SocketIORoomStr.from_project_id(project_id),
        message=message,
        ignore_queue=False,
    )
