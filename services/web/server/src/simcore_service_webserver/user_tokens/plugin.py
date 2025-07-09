import logging

from aiohttp import web
from servicelib.aiohttp.application_setup import ensure_single_setup

from ._controller import rest

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_user_tokens_feature(app: web.Application):
    app.add_routes(rest.routes)
