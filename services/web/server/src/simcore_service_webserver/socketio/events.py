"""
This module takes care of sending events to the connected webclient through the socket.io interface
"""

import logging
from collections import deque
from typing import Any, Final, Sequence, TypedDict

from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.json_serialization import json_dumps
from servicelib.utils import fire_and_forget_task, logged_gather

from ..resource_manager.websocket_manager import managed_resource
from .server import AsyncServer, get_socket_server

log = logging.getLogger(__name__)

SOCKET_IO_PROJECT_UPDATED_EVENT: str = "projectStateUpdated"
SOCKET_IO_NODE_UPDATED_EVENT: str = "nodeUpdated"
SOCKET_IO_LOG_EVENT: str = "logger"
SOCKET_IO_HEARTBEAT_EVENT: str = "set_heartbeat_emit_interval"
SOCKET_IO_EVENT: str = "event"
SOCKET_IO_NODE_PROGRESS_EVENT: Final[str] = "nodeProgress"


class SocketMessageDict(TypedDict):
    event_type: str
    data: dict[str, Any]


async def send_messages(
    app: Application, user_id: str, messages: Sequence[SocketMessageDict]
) -> None:
    sio: AsyncServer = get_socket_server(app)

    socket_ids: list[str] = []
    with managed_resource(user_id, None, app) as rt:
        socket_ids = await rt.find_socket_ids()

    send_tasks = deque()
    for sid in socket_ids:
        for message in messages:
            send_tasks.append(
                sio.emit(message["event_type"], json_dumps(message["data"]), room=sid)
            )
    await logged_gather(*send_tasks, reraise=False, log=log, max_concurrency=10)


async def post_messages(
    app: Application, user_id: str, messages: Sequence[SocketMessageDict]
) -> None:
    fire_and_forget_task(
        send_messages(app, user_id, messages),
        task_suffix_name=f"post_message_{user_id=}",
        fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )


async def post_group_messages(
    app: Application, room: str, messages: Sequence[SocketMessageDict]
) -> None:
    fire_and_forget_task(
        send_group_messages(app, room, messages),
        task_suffix_name=f"post_group_messages_{room=}",
        fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )


async def send_group_messages(
    app: Application, room: str, messages: Sequence[SocketMessageDict]
) -> None:
    sio: AsyncServer = get_socket_server(app)
    send_tasks = [
        sio.emit(message["event_type"], json_dumps(message["data"]), room=room)
        for message in messages
    ]

    await logged_gather(*send_tasks, reraise=False, log=log, max_concurrency=10)
