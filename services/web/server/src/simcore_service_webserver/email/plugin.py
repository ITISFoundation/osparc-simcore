""" Plugin to send emails and render email templates


 SMTP: Simple Mail Transfer Protocol
 MIME: Multipurpose Internet Mail Extensions

"""
import logging

import aiohttp_jinja2
import jinja_app_loader
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .._resources import webserver_resources
from . import _handlers

log = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_EMAIL", logger=log
)
def setup_email(app: web.Application):
    """
    Email template and helper functions to send emails
    """

    templates_dir = webserver_resources.get_path("templates")
    if not templates_dir.exists():
        msg = f"Cannot find email templates directory '{templates_dir}'"
        raise FileNotFoundError(msg)

    # SEE https://github.com/aio-libs/aiohttp-jinja2
    env = aiohttp_jinja2.setup(app, loader=jinja_app_loader.Loader())
    assert env  # nosec

    # routings
    app.router.add_routes(_handlers.routes)
