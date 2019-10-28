""" Subsystem that renders and sends emails


"""
import logging

import aiohttp_jinja2
#import jinja2 TODO: check
import jinja_app_loader
from aiohttp import web

from servicelib.application_setup import ModuleCategory, mark_as_module_setup

from .resources import resources

# TODO: move login/utils.py email functionality here!
#from email.mime.text import MIMEText
#import aiosmtplib


log = logging.getLogger(__name__)


@mark_as_module_setup("db", ModuleCategory.ADDON, logger=log)
def setup(app: web.Application, debug: bool=False):
    tmpl_dir = resources.get_path('templates')
    if not tmpl_dir.exists():
        log.error("Cannot find email templates in '%s'", tmpl_dir)
        return False

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
