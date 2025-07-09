import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ensure_single_setup

from . import _controller_rest
from ._models import overwrite_user_preferences_defaults

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_user_preferences(app: web.Application):

    overwrite_user_preferences_defaults(app)
    app.router.add_routes(_controller_rest.routes)
