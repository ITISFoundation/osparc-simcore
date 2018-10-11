import logging
from aiohttp import web

log = logging.getLogger(__name__)

def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    # collect here all maps and join in the router


setup_rest = setup

__all__ = (
    'setup', 'setup_rest'
)
