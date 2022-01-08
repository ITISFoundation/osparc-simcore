""" Subsystem that renders and sends emails


"""
import logging

import aiohttp_jinja2
import jinja_app_loader
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from .resources import resources

# TODO: move login/utils.py email functionality here!
# from email.mime.text import MIMEText
# import aiosmtplib
# import jinja2 TODO: check

log = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, config_section="WEBSERVER_EMAIL", logger=log
)
def setup_email(app: web.Application, debug: bool = False):

    templates_dir = resources.get_path("templates")
    if not templates_dir.exists():
        log.error("Cannot find email templates in '%s'", templates_dir)
        return False

    env = aiohttp_jinja2.setup(
        app,
        loader=jinja_app_loader.Loader(),  # jinja2.FileSystemLoader(tmpl_dir)
        auto_reload=debug,
    )

    return env
