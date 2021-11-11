"""
This module takes care of sending events to the connected webclient through the socket.io interface
"""

import json
import logging
from collections import deque
from typing import Any, Deque, Dict, List

from aiohttp.web import Application
from servicelib.utils import fire_and_forget_task, logged_gather

from ..resource_manager.websocket_manager import managed_resource
from .config import AsyncServer, get_socket_server

log = logging.getLogger(__name__)

SOCKET_IO_PROJECT_UPDATED_EVENT: str = "projectStateUpdated"
SOCKET_IO_NODE_UPDATED_EVENT: str = "nodeUpdated"
SOCKET_IO_LOG_EVENT: str = "logger"


async def send_messages(
    app: Application, user_id: str, messages: Dict[str, Any]
) -> None:
    sio: AsyncServer = get_socket_server(app)

    socket_ids: List[str] = []
    with managed_resource(user_id, None, app) as rt:
        socket_ids = await rt.find_socket_ids()

    send_tasks = deque()
    for sid in socket_ids:
        for event_name, data in messages.items():
            send_tasks.append(sio.emit(event_name, json.dumps(data), room=sid))
    await logged_gather(*send_tasks, reraise=False, log=log, max_concurrency=10)


async def post_messages(
    app: Application, user_id: str, messages: Dict[str, Any]
) -> None:
    sio: AsyncServer = get_socket_server(app)

    socket_ids: List[str] = []
    with managed_resource(user_id, None, app) as rt:
        socket_ids = await rt.find_socket_ids()
    for sid in socket_ids:
        # We only send the data to the right sockets
        # Notice that there might be several tabs open
        for event_name, data in messages.items():
            fire_and_forget_task(sio.emit(event_name, json.dumps(data), room=sid))


async def post_group_messages(
    app: Application, room: str, messages: Dict[str, Any]
) -> None:
    sio: AsyncServer = get_socket_server(app)
    for event_name, data in messages.items():
        fire_and_forget_task(sio.emit(event_name, json.dumps(data), room=room))
