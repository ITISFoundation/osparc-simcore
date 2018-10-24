import logging

import aiohttp_jinja2
from aiohttp import web

#import jinja2
import jinja_app_loader

from .resources import resources

log = logging.getLogger(__name__)

def setup(app: web.Application, debug: bool=False):
    log.debug("Setting up %s ...", __name__)

    tmpl_dir = resources.get_path('templates')
    assert tmpl_dir.exists()

    env = aiohttp_jinja2.setup(
        app,
        loader=jinja_app_loader.Loader(), #jinja2.FileSystemLoader(tmpl_dir)
        auto_reload=debug
    )
    return env

# alias
setup_render = setup


__all__ = (
    'setup_render'
)
