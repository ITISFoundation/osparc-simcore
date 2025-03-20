from aiohttp import web

from ..rest.plugin import setup_rest
from . import _rest


def setup_tasks(app: web.Application):
    setup_rest(app)
    app.router.add_routes(_rest.routes)
