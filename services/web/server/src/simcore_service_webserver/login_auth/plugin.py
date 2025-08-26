import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ensure_single_setup

from ..products.plugin import setup_products_without_rpc
from ..rest.plugin import setup_rest
from ..security.plugin import setup_security
from . import _controller_rest

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_login_auth(app: web.Application):
    setup_products_without_rpc(app)
    setup_security(app)
    setup_rest(app)

    app.add_routes(_controller_rest.routes)
