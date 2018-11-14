""" Subsystem that renders and sends emails


"""
import logging

import aiohttp_jinja2
#import jinja2 TODO: check
import jinja_app_loader
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY

from .email_config import CONFIG_SECTION_NAME
from .resources import resources

# TODO: move login/utils.py email functionality here!
#from email.mime.text import MIMEText
#import aiosmtplib


log = logging.getLogger(__name__)



def setup(app: web.Application, debug: bool=False):
    log.debug("Setting up %s ...", __name__)

    assert CONFIG_SECTION_NAME in app[APP_CONFIG_KEY]

    tmpl_dir = resources.get_path('templates')
    assert tmpl_dir.exists()

    env = aiohttp_jinja2.setup(
        app,
        loader=jinja_app_loader.Loader(), #jinja2.FileSystemLoader(tmpl_dir)
        auto_reload=debug
    )

    return env

# alias
setup_email = setup


__all__ = (
    'setup_email'
)
