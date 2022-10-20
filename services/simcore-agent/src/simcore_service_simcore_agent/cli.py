import logging

import typer
from settings_library.utils_cli import create_settings_command

from ._meta import APP_NAME
from .app import create_application
from .settings import ApplicationSettings

log = logging.getLogger(__name__)

main = typer.Typer(name=APP_NAME)

main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@main.command()
def run():
    """Runs application"""
    create_application().run()
