import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ensure_single_setup

from . import _controller_rest

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_user_notification_feature(app: web.Application):

    app.router.add_routes(_controller_rest.routes)
