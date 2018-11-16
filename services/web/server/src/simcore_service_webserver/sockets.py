""" socket io subsystem


"""
import logging

from aiohttp import web

from .sockets_handlers import sio


log = logging.getLogger(__name__)


def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    sio.attach(app)


# alias
setup_sockets = setup


__all__ = (
    "setup_sockets"
)
