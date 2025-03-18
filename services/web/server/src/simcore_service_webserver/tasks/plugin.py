import logging

from aiohttp import web

from ..rest.plugin import setup_rest
from . import _rest

_logger = logging.getLogger(__name__)


# @app_module_setup(
#    __name__, ModuleCategory.ADDON, logger=_logger
# )
def setup_tasks(app: web.Application):
    setup_rest(app)
    app.router.add_routes(_rest.routes)
