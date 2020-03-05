"""
This module takes care of sending events to the connected webclient through the socket.io interface
"""

import asyncio
import json
from typing import Any, Dict, List

from aiohttp.web import Application

from ..resource_manager.websocket_manager import managed_resource
from .config import AsyncServer, get_socket_server



async def post_messages(
    app: Application, user_id: str, messages: Dict[str, Any]
) -> None:
    sio: AsyncServer = get_socket_server(app)

    with managed_resource(user_id, None, app) as registry:
        socket_ids: List[str] = await registry.find_socket_ids()
        for sid in socket_ids:
            # We only send the data to the right sockets
            # Notice that there might be several tabs open
            tasks = [
                sio.emit(event_name, json.dumps(data), room=sid)
                for event_name, data in messages.items()
            ]
            asyncio.ensure_future(
                asyncio.gather(
                    *tasks
                )  # TODO: PC->SAN??, return_exceptions=True othewise will error '_GatheringFuture exception was never retrieved'
            )


# FIXME: PC->SAN: I wonder if here is the reason for this unhandled
#
# {
# "txt": "<Task finished coro=<WebSocket.wait() done, defined at /usr/local/lib/python3.6/site-packages/engineio/async_drivers/aiohttp.py:114> exception=OSError()>",
# "type": "<class '_asyncio.Task'>",
# "done": true,
# "cancelled": false,
# "stack": null,
# "exception": "<class 'OSError'>: "
# },
#  and https://github.com/miguelgrinberg/python-engineio/blob/master/engineio/async_drivers/aiohttp.py#L114) shows that ``IOError = OSError`` is raised
# when received data is corrupted!!
#
#
# It might be that sio.emit raise exception, which propagates throw gather
#
