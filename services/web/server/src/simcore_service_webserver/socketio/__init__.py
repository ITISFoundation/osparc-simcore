""" socket io subsystem


"""
import logging

from aiohttp import web

from servicelib.application_setup import ModuleCategory, app_module_setup

from .sockets_handlers import sio

log = logging.getLogger(__name__)


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    sio.attach(app)


# alias
setup_sockets = setup


__all__ = (
    "setup_sockets"
)
