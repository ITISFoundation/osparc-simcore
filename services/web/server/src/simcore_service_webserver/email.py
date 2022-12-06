""" Subsystem that renders and sends emails

"""
# TODO: move login/utils.py email functionality here!
# from email.mime.text import MIMEText
# import aiosmtplib
# import jinja2 TODO: check


from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp_jinja2
import jinja_app_loader
from aiohttp import web
from servicelib.aiohttp.application_setup import ModuleCategory, app_module_setup

from ._constants import APP_SETTINGS_KEY
from ._resources import resources

if TYPE_CHECKING:
    # SEE https://stackoverflow.com/questions/39740632/python-type-hinting-without-cyclic-imports
    # SEE https://peps.python.org/pep-0563/
    from .application_settings import ApplicationSettings

log = logging.getLogger(__name__)


@app_module_setup(
    __name__, ModuleCategory.ADDON, settings_name="WEBSERVER_EMAIL", logger=log
)
def setup_email(app: web.Application):
    settings: ApplicationSettings | None = app.get(APP_SETTINGS_KEY)

    templates_dir = resources.get_path("templates")
    if not templates_dir.exists():
        log.error("Cannot find email templates in '%s'", templates_dir)
        return False

    # SEE https://github.com/aio-libs/aiohttp-jinja2
    env = aiohttp_jinja2.setup(
        app,
        loader=jinja_app_loader.Loader(),  # jinja2.FileSystemLoader(templates_dir)
        auto_reload=settings
        and settings.SC_BOOT_MODE
        and settings.SC_BOOT_MODE.is_devel_mode(),
    )
    assert env  # nosec
