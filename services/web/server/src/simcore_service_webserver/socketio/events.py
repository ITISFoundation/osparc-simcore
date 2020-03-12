"""
This module takes care of sending events to the connected webclient through the socket.io interface
"""

import json
import logging
from typing import Any, Dict, List

from aiohttp.web import Application

from servicelib.utils import fire_and_forget_task

from ..resource_manager.websocket_manager import managed_resource
from .config import AsyncServer, get_socket_server

log = logging.getLogger(__name__)


async def post_messages(
    app: Application, user_id: str, messages: Dict[str, Any]
) -> None:
    sio: AsyncServer = get_socket_server(app)

    with managed_resource(user_id, None, app) as registry:
        socket_ids: List[str] = await registry.find_socket_ids()
        for sid in socket_ids:
            # We only send the data to the right sockets
            # Notice that there might be several tabs open
            for event_name, data in messages.items():
                fire_and_forget_task(sio.emit(event_name, json.dumps(data), room=sid))
