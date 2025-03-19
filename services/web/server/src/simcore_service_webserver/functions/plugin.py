from aiohttp import web

from . import _controller_rpc


def setup(app: web.Application):
    app.on_startup.append(_controller_rpc.register_rpc_routes_on_startup)
