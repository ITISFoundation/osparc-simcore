import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ensure_single_setup

from ._controller.rest import preregistration as _controller_rest_preregistration

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_login_account(app: web.Application):
    app.add_routes(_controller_rest_preregistration.routes)
