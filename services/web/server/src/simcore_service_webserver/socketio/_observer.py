""" Observer events handlers

SEE servicelib.observer
"""

import asyncio
import logging

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.logging_utils import get_log_record_extra
from servicelib.observer import observe
from servicelib.utils import fire_and_forget_task, logged_gather
from socketio import AsyncServer

from ..resource_manager.websocket_manager import managed_resource
from ._utils import get_socket_server

_logger = logging.getLogger(__name__)


async def _disconnect_other_sockets(sio: AsyncServer, sockets: list[str]) -> None:
    _logger.debug("disconnecting sockets %s", sockets)
    logout_tasks = [
        sio.emit("logout", to=sid, data={"reason": "user logged out"})
        for sid in sockets
    ]
    await logged_gather(*logout_tasks, reraise=False)

    # let the client react
    await asyncio.sleep(3)
    # ensure disconnection is effective
    disconnect_tasks = [sio.disconnect(sid=sid) for sid in sockets]
    await logged_gather(*disconnect_tasks)


@observe(event="SIGNAL_USER_LOGOUT")
async def on_user_logout(
    user_id: str, client_session_id: str | None, app: web.Application
) -> None:
    _logger.debug("user %s must be disconnected", user_id)
    # find the sockets related to the user
    sio: AsyncServer = get_socket_server(app)
    with managed_resource(user_id, client_session_id, app) as rt:
        # start by disconnecting this client if possible
        if client_session_id:
            if socket_id := await rt.get_socket_id():
                try:
                    await sio.disconnect(sid=socket_id)
                except KeyError as exc:
                    _logger.warning(
                        "Disconnection of socket id '%s' failed. socket id could not be found: [%s]",
                        socket_id,
                        exc,
                        extra=get_log_record_extra(user_id=user_id),
                    )
            # trigger faster gc on disconnect
            await rt.user_pressed_disconnect()

        # now let's give a chance to all the clients to properly logout
        sockets = await rt.find_socket_ids()
        if sockets:
            # let's do it as a task so it does not block us here
            fire_and_forget_task(
                _disconnect_other_sockets(sio, sockets),
                task_suffix_name=f"disconnect_other_sockets_{user_id=}",
                fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
            )
