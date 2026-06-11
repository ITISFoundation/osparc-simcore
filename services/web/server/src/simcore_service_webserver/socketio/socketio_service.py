"""Socketio public facade per DESIGN.md §133-152."""

from ._utils import (
    CLIENT_SOCKET_SERVER_APPKEY,
    EnvironDict,
    SocketID,
    SocketioConnectEventHandler,
    SocketioDisconnectEventHandler,
    SocketioEventHandler,
    get_socket_server,
    register_socketio_handlers,
)
from .messages import (
    SOCKET_IO_EVENT,
    SOCKET_IO_HEARTBEAT_EVENT,
    SOCKET_IO_LOG_EVENT,
    SOCKET_IO_NODE_UPDATED_EVENT,
    SOCKET_IO_PROJECT_UPDATED_EVENT,
    SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT,
    send_message_to_project_room,
    send_message_to_standard_group,
    send_message_to_user,
)
from .models import (
    WebSocketNodeProgress,
    WebSocketProjectProgress,
)
from .plugin import setup_socketio

__all__: tuple[str, ...] = (
    # constants
    "CLIENT_SOCKET_SERVER_APPKEY",
    "SOCKET_IO_EVENT",
    "SOCKET_IO_HEARTBEAT_EVENT",
    "SOCKET_IO_LOG_EVENT",
    "SOCKET_IO_NODE_UPDATED_EVENT",
    "SOCKET_IO_PROJECT_UPDATED_EVENT",
    "SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT",
    # types
    "EnvironDict",
    "SocketID",
    "SocketioConnectEventHandler",
    "SocketioDisconnectEventHandler",
    "SocketioEventHandler",
    # models
    "WebSocketNodeProgress",
    "WebSocketProjectProgress",
    # functions
    "get_socket_server",
    "register_socketio_handlers",
    "send_message_to_project_room",
    "send_message_to_standard_group",
    "send_message_to_user",
    "setup_socketio",
)  # nopycln: file
