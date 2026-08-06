"""
Socket.IO event constants and message types

This module defines all Socket.IO event names used throughout the socketio subsystem.
"""

from typing import Final

#
# Socket-IO event names
#
SOCKET_IO_EVENT: Final[str] = "event"
SOCKET_IO_HEARTBEAT_EVENT: Final[str] = "set_heartbeat_emit_interval"
SOCKET_IO_LOG_EVENT: Final[str] = "logger"
SOCKET_IO_NODE_UPDATED_EVENT: Final[str] = "nodeUpdated"
SOCKET_IO_PROJECT_UPDATED_EVENT: Final[str] = "projectStateUpdated"
SOCKET_IO_WALLET_OSPARC_CREDITS_UPDATED_EVENT: Final[str] = "walletOsparcCreditsUpdated"
