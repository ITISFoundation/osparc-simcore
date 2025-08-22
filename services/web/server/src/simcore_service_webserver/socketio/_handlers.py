"""Defines **async** handlers for socket.io server

SEE https://pypi.python.org/pypi/python-socketio
SEE http://python-socketio.readthedocs.io/en/latest/
"""

import contextlib
import logging
from typing import Any

import socketio.exceptions  # type: ignore[import-untyped]
from aiohttp import web
from models_library.api_schemas_webserver.socketio import SocketIORoomStr
from models_library.products import ProductName
from models_library.socketio import SocketMessageDict
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.aiohttp.observer import emit
from servicelib.logging_errors import create_troubleshootting_log_kwargs
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.request_keys import RQT_USERID_KEY

from ..groups.api import list_user_groups_ids_with_read_access
from ..login.decorators import login_required
from ..products import products_web
from ..resource_manager.user_sessions import managed_resource
from ._utils import EnvironDict, SocketID, get_socket_server, register_socketio_handler
from .messages import SOCKET_IO_HEARTBEAT_EVENT, send_message_to_user

_logger = logging.getLogger(__name__)

_ANONYMOUS_USER_ID = -1

# Messages reaching users
_MSG_UNAUTHORIZED_MISSING_SESSION_INFO = (
    "Sorry, we cannot identify you. Please reaload the page and login again."
)


# Send service_deletion_timeout to client
# 2 seconds avoids GC from removing the services to early
# this has been tested and is working with good results
# the previous implementation was not working as expected
_EMIT_INTERVAL_S: int = 2


def auth_user_factory(socket_id: SocketID):
    @login_required
    async def _handler(request: web.Request) -> tuple[UserID, ProductName, str]:
        """
        Raises:
            web.HTTPUnauthorized: when the user is not recognized. Keeps the original request
        """
        app = request.app
        user_id = TypeAdapter(UserID).validate_python(
            request.get(RQT_USERID_KEY, _ANONYMOUS_USER_ID)
        )
        client_session_id = request.query.get("client_session_id", None)
        product = products_web.get_current_product(request)

        _logger.debug(
            "client %s,%s authenticated", f"{user_id=}", f"{client_session_id=}"
        )

        if not client_session_id:
            _logger.error(
                "Tab ID is missing", extra=get_log_record_extra(user_id=user_id)
            )
            raise web.HTTPUnauthorized(text=_MSG_UNAUTHORIZED_MISSING_SESSION_INFO)

        # here we keep the original HTTP request in the socket session storage
        sio = get_socket_server(app)
        async with sio.session(socket_id) as socketio_session:
            socketio_session["user_id"] = user_id
            socketio_session["client_session_id"] = client_session_id
            socketio_session["request"] = request
            socketio_session["product_name"] = product.name

        # REDIS wrapper
        with managed_resource(user_id, client_session_id, app) as resource_registry:
            await resource_registry.set_socket_id(socket_id)

        return user_id, product.name, client_session_id

    return _handler


async def _set_user_in_group_rooms(
    app: web.Application, user_id: UserID, socket_id: SocketID
) -> None:
    """Adds user in rooms associated to its groups"""

    group_ids = await list_user_groups_ids_with_read_access(app, user_id=user_id)

    sio = get_socket_server(app)
    for gid in group_ids:
        await sio.enter_room(socket_id, SocketIORoomStr.from_group_id(gid))

    await sio.enter_room(socket_id, SocketIORoomStr.from_user_id(user_id))


#
# socketio event handlers
#


@register_socketio_handler
async def connect(
    socket_id: SocketID, environ: EnvironDict, app: web.Application
) -> bool:
    """socketio reserved handler for when the fontend connects through socket.io

    Arguments:
        environ -- the WSGI environ, among other contains the original request

    Raises:
        SIoConnectionRefusedError: HTTPUnauthorized
        SIoConnectionRefusedError: Unexpected error

    Returns:
        True if socket.io connection accepted
    """
    _logger.debug("client connecting in room %s", f"{socket_id=}")

    try:
        auth_user_handler = auth_user_factory(socket_id)
        user_id, product_name, client_session_id = await auth_user_handler(
            environ["aiohttp.request"]
        )
        _logger.info(
            "%s successfully connected with %s",
            f"{user_id=}",
            f"{client_session_id=}",
            extra=get_log_record_extra(user_id=user_id),
        )

        await _set_user_in_group_rooms(app, user_id, socket_id)

        _logger.debug("Sending set_heartbeat_emit_interval with %s", _EMIT_INTERVAL_S)

        await emit(
            app, "SIGNAL_USER_CONNECTED", user_id, app, product_name, client_session_id
        )

        await send_message_to_user(
            app,
            user_id,
            message=SocketMessageDict(
                event_type=SOCKET_IO_HEARTBEAT_EVENT,
                data={"interval": _EMIT_INTERVAL_S},
            ),
            ignore_queue=True,
        )

    except web.HTTPUnauthorized as exc:
        msg = "authentification failed"
        raise socketio.exceptions.ConnectionRefusedError(msg) from exc
    except Exception as exc:  # pylint: disable=broad-except
        msg = f"Unexpected error: {exc}"
        raise socketio.exceptions.ConnectionRefusedError(msg) from exc

    return True


@register_socketio_handler
async def disconnect(socket_id: SocketID, app: web.Application) -> None:
    """socketio reserved handler for when the socket.io connection is disconnected."""
    async with contextlib.AsyncExitStack() as stack:
        # retrieve the socket session
        try:
            socketio_session = await stack.enter_async_context(
                get_socket_server(app).session(socket_id)
            )

        except KeyError as err:
            _logger.warning(
                **create_troubleshootting_log_kwargs(
                    f"Socket session {socket_id} not found during disconnect, already cleaned up",
                    error=err,
                    error_context={"socket_id": socket_id},
                )
            )
            return

        # session is wel formed, we can access its data
        try:
            user_id = socketio_session["user_id"]
            client_session_id = socketio_session["client_session_id"]
            product_name = socketio_session["product_name"]

        except KeyError as err:
            _logger.exception(
                **create_troubleshootting_log_kwargs(
                    f"Socket session {socket_id} does not have user_id or client_session_id during disconnect",
                    error=err,
                    error_context={
                        "socket_id": socket_id,
                        "socketio_session": socketio_session,
                    },
                    tip="Check if session is corrupted",
                )
            )
            return

        # Disconnecting
        with log_context(
            _logger,
            logging.INFO,
            "disconnection of %s with %s",
            f"{user_id=}",
            f"{client_session_id=}",
        ):
            with managed_resource(user_id, client_session_id, app) as user_session:
                await user_session.remove_socket_id()

            # signal same user other clients if available
            await emit(
                app,
                "SIGNAL_USER_DISCONNECTED",
                user_id,
                client_session_id,
                app,
                product_name,
            )


@register_socketio_handler
async def client_heartbeat(socket_id: SocketID, _: Any, app: web.Application) -> None:
    """JS client invokes this handler to signal its presence.

    Each time this event is received the alive key's TTL is updated in
    Redis. Once the key expires, resources will be garbage collected.

    Arguments:
        sid-- the socket ID
        _  -- the data is ignored for this handler
        app  -- the aiohttp app
    """
    sio = get_socket_server(app)
    async with sio.session(socket_id) as socketio_session:
        if user_id := socketio_session.get("user_id"):
            client_session_id = socketio_session["client_session_id"]

            with managed_resource(user_id, client_session_id, app) as rt:
                await rt.set_heartbeat()
