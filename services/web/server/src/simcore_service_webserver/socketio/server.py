from aiohttp import web
from socketio import AsyncServer

APP_CLIENT_SOCKET_SERVER_KEY = f"{__name__}.socketio_socketio"
APP_CLIENT_SOCKET_DECORATED_HANDLERS_KEY = f"{__name__}.socketio_handlers"


def get_socket_server(app: web.Application) -> AsyncServer:
    return app[APP_CLIENT_SOCKET_SERVER_KEY]
