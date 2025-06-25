import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ensure_single_setup

from ..products.plugin import setup_products
from ..rest.plugin import setup_rest
from ..security.plugin import setup_security
from . import _controller_rest

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_login_auth(app: web.Application):
    setup_products(app, rpc_enabled=False)
    setup_security(app)
    setup_rest(app)

    app.add_routes(_controller_rest.routes)
