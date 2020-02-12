"""
This module takes care of sending events to the connected webclient through the socket.io interface.
"""

import asyncio
import json
from typing import Any, Dict

from aiohttp import web

from ..resource_manager.websocket_manager import managed_resource
from .config import get_socket_server


async def post_messages(app: web.Application, user_id: str, messages: Dict[str, Any]) -> None:
    sio = get_socket_server(app)
    with managed_resource(user_id, None, app) as rt:
        socket_ids = await rt.find_socket_ids()
        for sid in socket_ids:
            # we only send the data to the right sockets (there might be several tabs open)
            tasks = [sio.emit(event, json.dumps(data), room=sid) for event, data in messages.items()]
            asyncio.ensure_future(asyncio.gather(*tasks))
