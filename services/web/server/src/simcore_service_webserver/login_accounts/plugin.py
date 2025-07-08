import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ensure_single_setup

from . import _controler_rest

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_login_account(app: web.Application):
    app.add_routes(_controler_rest.routes)
