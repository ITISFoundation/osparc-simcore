import logging

from aiohttp import web

from ..application_setup import ensure_single_setup
from ._controller.rest import user_tokens_rest

_logger = logging.getLogger(__name__)


@ensure_single_setup(__name__, logger=_logger)
def setup_user_tokens_feature(app: web.Application):
    app.add_routes(user_tokens_rest.routes)
